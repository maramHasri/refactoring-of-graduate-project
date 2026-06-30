"""
Academic RBAC: workspace role vs subject_memberships.subject_role.

Workspace permissions use membership.role (ADMIN, TEACHER, STUDENT).
Subject permissions use subject_memberships.subject_role (TEACHER, STUDENT).
"""
from models import Membership, Subject, SubjectMembership, Workspace
from utils.enums import MembershipRole, QuestionBankVisibility, SubjectRole
from utils.rbac import can_manage_workspace_settings, is_workspace_owner


def can_manage_subjects(workspace: Workspace, membership: Membership | None) -> bool:
    """Owner or ADMIN may create/update/archive subjects and assign teachers."""
    return can_manage_workspace_settings(workspace, membership)


def has_subject_role(
    subject_membership: SubjectMembership | None,
    *,
    role: str,
) -> bool:
    if not subject_membership or subject_membership.deleted_at is not None:
        return False
    if subject_membership.status != "ACTIVE":
        return False
    return subject_membership.subject_role == role


def verify_subject_teacher_access(
    subject_membership: SubjectMembership | None,
) -> bool:
    """Teacher assigned to subject (subject_role=TEACHER) may create banks/exams."""
    return has_subject_role(subject_membership, role=SubjectRole.TEACHER.value)


def verify_subject_student_access(
    subject_membership: SubjectMembership | None,
) -> bool:
    return has_subject_role(subject_membership, role=SubjectRole.STUDENT.value)


def can_take_published_test(
    workspace: Workspace,
    actor: Membership | None,
    actor_subject_link: SubjectMembership | None,
) -> bool:
    """Students enrolled in the test subject may start or resume attempts."""
    if can_manage_subjects(workspace, actor):
        return True
    return verify_subject_student_access(actor_subject_link)


def can_view_attempt_grading(
    workspace: Workspace,
    actor: Membership | None,
    *,
    actor_subject_link: SubjectMembership | None,
    is_test_creator: bool,
) -> bool:
    """Test creator, subject teacher, or workspace admin may view grading results."""
    if can_manage_subjects(workspace, actor) or is_test_creator:
        return True
    return verify_subject_teacher_access(actor_subject_link)


def can_manage_test_attempts(
    workspace: Workspace,
    actor: Membership | None,
    *,
    actor_subject_link: SubjectMembership | None,
    is_test_creator: bool,
) -> bool:
    """Teachers, admins, or test creator may force-submit and list attempts."""
    return can_view_attempt_grading(
        workspace,
        actor,
        actor_subject_link=actor_subject_link,
        is_test_creator=is_test_creator,
    )


def can_assign_teachers_to_subject(
    workspace: Workspace, membership: Membership | None
) -> bool:
    return can_manage_subjects(workspace, membership)


def can_enroll_students_in_subject(
    workspace: Workspace,
    actor: Membership | None,
    actor_subject_link: SubjectMembership | None,
) -> bool:
    if can_manage_subjects(workspace, actor):
        return True
    return verify_subject_teacher_access(actor_subject_link)


def can_view_question_bank(
    bank_visibility: str,
    *,
    workspace: Workspace,
    actor: Membership | None,
    actor_subject_link: SubjectMembership | None,
    is_bank_creator: bool,
) -> bool:
    if bank_visibility == QuestionBankVisibility.PRIVATE.value:
        return is_bank_creator or can_manage_subjects(workspace, actor)
    if bank_visibility == QuestionBankVisibility.WORKSPACE.value:
        if can_manage_subjects(workspace, actor):
            return True
        return actor_subject_link is not None and actor_subject_link.deleted_at is None
    if bank_visibility == QuestionBankVisibility.COMMUNITY.value:
        return True
    return False


def can_modify_question_bank(
    workspace: Workspace,
    actor: Membership | None,
    *,
    is_bank_creator: bool,
) -> bool:
    return is_bank_creator or can_manage_subjects(workspace, actor)


def can_view_subject_topics(
    workspace: Workspace,
    actor_subject_link: SubjectMembership | None,
    *,
    actor: Membership | None = None,
) -> bool:
    """List/use topics: workspace admin/owner or any active subject assignment."""
    if can_manage_subjects(workspace, actor):
        return True
    return actor_subject_link is not None


def can_manage_subject_topics(
    workspace: Workspace,
    actor_subject_link: SubjectMembership | None,
    *,
    actor: Membership | None = None,
) -> bool:
    """Create/update/delete topics: workspace admin/owner or subject TEACHER."""
    if can_manage_subjects(workspace, actor):
        return True
    return verify_subject_teacher_access(actor_subject_link)
