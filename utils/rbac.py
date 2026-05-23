"""
RBAC helpers — roles are fixed: ADMIN, TEACHER, STUDENT.
Owner is NOT a role; use workspace.owner_membership_id.
"""
from models import Membership, Workspace
from utils.enums import MembershipRole


def is_workspace_owner(workspace: Workspace, membership: Membership | None) -> bool:
    if not membership:
        return False
    return workspace.owner_membership_id == membership.id


def has_admin_role(membership: Membership | None) -> bool:
    return membership is not None and membership.role == MembershipRole.ADMIN.value


def has_teacher_or_admin_role(membership: Membership | None) -> bool:
    if not membership:
        return False
    return membership.role in (
        MembershipRole.ADMIN.value,
        MembershipRole.TEACHER.value,
    )


def can_manage_workspace_settings(workspace: Workspace, membership: Membership | None) -> bool:
    return has_admin_role(membership) or is_workspace_owner(workspace, membership)


def can_invite_with_role(
    inviter_role: str | None, assigned_role: str, *, is_superadmin: bool = False
) -> bool:
    """
    ADMIN may invite ADMIN/TEACHER/STUDENT.
    TEACHER may invite STUDENT only.
    STUDENT cannot invite.
    """
    if is_superadmin:
        return True
    if inviter_role is None:
        return False
    if inviter_role == MembershipRole.STUDENT.value:
        return False
    if inviter_role == MembershipRole.TEACHER.value:
        return assigned_role == MembershipRole.STUDENT.value
    if inviter_role == MembershipRole.ADMIN.value:
        return assigned_role in (
            MembershipRole.ADMIN.value,
            MembershipRole.TEACHER.value,
            MembershipRole.STUDENT.value,
        )
    return False
