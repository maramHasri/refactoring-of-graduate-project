"""
Subject lifecycle and subject_memberships (teacher/student assignments).
"""
from datetime import datetime, timezone

from models import Subject, SubjectMembership
from repositories.subject_repository import (
    SubjectMembershipRepository,
    SubjectRepository,
)
from repositories.workspace_repository import MembershipRepository, WorkspaceRepository
from service.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from utils.academic_rbac import (
    can_assign_teachers_to_subject,
    can_enroll_students_in_subject,
    can_manage_subjects,
    verify_subject_teacher_access,
)
from utils.db import db
from utils.enums import MembershipRole, SubjectMembershipStatus, SubjectRole


class SubjectService:
    def __init__(self):
        self.subjects = SubjectRepository()
        self.subject_memberships = SubjectMembershipRepository()
        self.memberships = MembershipRepository()
        self.workspaces = WorkspaceRepository()

    def create_subject(
        self,
        *,
        workspace_id: int,
        name: str,
        actor_membership,
        code: str | None = None,
        description: str | None = None,
    ) -> Subject:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")
        if not can_manage_subjects(workspace, actor_membership):
            raise ForbiddenError("Only workspace owner or admin can create subjects")

        name = name.strip()
        if self.subjects.find_by_workspace_and_name(workspace_id, name):
            raise ConflictError("A subject with this name already exists in the workspace")

        subject = Subject(
            name=name,
            workspace_id=workspace_id,
            code=code.strip() if code else None,
            description=description,
            created_by_membership_id=actor_membership.id,
        )
        self.subjects.add(subject)
        db.session.commit()
        return subject

    def list_workspace_subjects(self, workspace_id: int, actor_membership) -> list[dict]:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")

        if can_manage_subjects(workspace, actor_membership):
            rows = self.subjects.list_active_by_workspace(workspace_id)
            return [self._serialize_subject(s) for s in rows]

        if actor_membership.role == MembershipRole.TEACHER.value:
            links = self._subjects_for_membership(actor_membership.id, workspace_id)
            return [self._serialize_subject(s) for s in links]

        if actor_membership.role == MembershipRole.STUDENT.value:
            links = self._subjects_for_membership(actor_membership.id, workspace_id)
            return [self._serialize_subject(s) for s in links]

        raise ForbiddenError("Insufficient permissions to list subjects")

    def get_subject(
        self, subject_id: int, workspace_id: int, actor_membership
    ) -> dict:
        subject = self._get_subject_or_404(subject_id, workspace_id)
        self._ensure_can_view_subject(subject, actor_membership)
        return self._serialize_subject(subject)

    def update_subject(
        self,
        subject_id: int,
        workspace_id: int,
        actor_membership,
        data: dict,
    ) -> Subject:
        workspace = self.workspaces.get_by_id(workspace_id)
        subject = self._get_subject_or_404(subject_id, workspace_id)
        if not can_manage_subjects(workspace, actor_membership):
            raise ForbiddenError("Only workspace owner or admin can update subjects")

        if "name" in data and data["name"]:
            name = data["name"].strip()
            existing = self.subjects.find_by_workspace_and_name(workspace_id, name)
            if existing and existing.id != subject.id:
                raise ConflictError("A subject with this name already exists")
            subject.name = name
        if "code" in data:
            subject.code = data["code"]
        if "description" in data:
            subject.description = data["description"]
        if "is_archived" in data and data["is_archived"] is not None:
            subject.is_archived = bool(data["is_archived"])

        db.session.commit()
        return subject

    def archive_subject(
        self, subject_id: int, workspace_id: int, actor_membership
    ) -> Subject:
        workspace = self.workspaces.get_by_id(workspace_id)
        subject = self._get_subject_or_404(subject_id, workspace_id)
        if not can_manage_subjects(workspace, actor_membership):
            raise ForbiddenError("Only workspace owner or admin can archive subjects")

        now = datetime.now(timezone.utc)
        subject.is_archived = True
        subject.deleted_at = now
        db.session.commit()
        return subject

    def assign_teacher_to_subject(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        teacher_membership_id: int,
        actor_membership,
    ) -> SubjectMembership:
        workspace = self.workspaces.get_by_id(workspace_id)
        subject = self._get_subject_or_404(subject_id, workspace_id)
        if not can_assign_teachers_to_subject(workspace, actor_membership):
            raise ForbiddenError("Only workspace owner or admin can assign teachers")

        teacher = self.memberships.get_by_id(teacher_membership_id)
        if not teacher or teacher.workspace_id != workspace_id:
            raise NotFoundError("Membership not found in this workspace")
        if teacher.status != "ACTIVE":
            raise ValidationError("Membership is not active")
        if teacher.role not in (
            MembershipRole.TEACHER.value,
            MembershipRole.ADMIN.value,
        ):
            raise ValidationError(
                "Only workspace teachers or admins can be assigned as subject teachers"
            )

        if self.subject_memberships.find_active(teacher_membership_id, subject_id):
            raise ConflictError("Teacher is already assigned to this subject")

        link = SubjectMembership(
            subject_id=subject_id,
            membership_id=teacher_membership_id,
            subject_role=SubjectRole.TEACHER.value,
            assigned_by_membership_id=actor_membership.id,
            status=SubjectMembershipStatus.ACTIVE.value,
        )
        self.subject_memberships.add(link)
        db.session.commit()
        return link

    def remove_teacher_from_subject(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        teacher_membership_id: int,
        actor_membership,
    ) -> None:
        workspace = self.workspaces.get_by_id(workspace_id)
        self._get_subject_or_404(subject_id, workspace_id)
        if not can_assign_teachers_to_subject(workspace, actor_membership):
            raise ForbiddenError("Only workspace owner or admin can remove teachers")

        link = self.subject_memberships.find_active_by_role(
            teacher_membership_id, subject_id, SubjectRole.TEACHER.value
        )
        if not link:
            raise NotFoundError("Teacher assignment not found")
        self.subject_memberships.soft_remove(link)
        db.session.commit()

    def list_subject_teachers(
        self, subject_id: int, workspace_id: int, actor_membership
    ) -> list[dict]:
        subject = self._get_subject_or_404(subject_id, workspace_id)
        self._ensure_can_view_subject(subject, actor_membership)
        links = self.subject_memberships.list_teachers_for_subject(subject_id)
        return [self._serialize_assignment(link) for link in links]

    def enroll_student_in_subject(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        student_membership_id: int,
        actor_membership,
    ) -> SubjectMembership:
        workspace = self.workspaces.get_by_id(workspace_id)
        subject = self._get_subject_or_404(subject_id, workspace_id)
        actor_link = self.subject_memberships.find_active_by_role(
            actor_membership.id, subject_id, SubjectRole.TEACHER.value
        )
        if not can_enroll_students_in_subject(workspace, actor_membership, actor_link):
            raise ForbiddenError(
                "Only admin, owner, or assigned subject teachers can enroll students"
            )

        student = self.memberships.get_by_id(student_membership_id)
        if not student or student.workspace_id != workspace_id:
            raise NotFoundError("Membership not found in this workspace")
        if student.role != MembershipRole.STUDENT.value:
            raise ValidationError("Only students can be enrolled in a subject")
        if student.status != "ACTIVE":
            raise ValidationError("Membership is not active")

        if self.subject_memberships.find_active(student_membership_id, subject_id):
            raise ConflictError("Student is already enrolled in this subject")

        link = SubjectMembership(
            subject_id=subject_id,
            membership_id=student_membership_id,
            subject_role=SubjectRole.STUDENT.value,
            assigned_by_membership_id=actor_membership.id,
            status=SubjectMembershipStatus.ACTIVE.value,
        )
        self.subject_memberships.add(link)
        db.session.commit()
        return link

    def remove_student_from_subject(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        student_membership_id: int,
        actor_membership,
    ) -> None:
        workspace = self.workspaces.get_by_id(workspace_id)
        subject = self._get_subject_or_404(subject_id, workspace_id)
        actor_link = self.subject_memberships.find_active_by_role(
            actor_membership.id, subject_id, SubjectRole.TEACHER.value
        )
        if not can_enroll_students_in_subject(workspace, actor_membership, actor_link):
            raise ForbiddenError("Insufficient permissions to remove student enrollment")

        link = self.subject_memberships.find_active_by_role(
            student_membership_id, subject_id, SubjectRole.STUDENT.value
        )
        if not link:
            raise NotFoundError("Student enrollment not found")
        self.subject_memberships.soft_remove(link)
        db.session.commit()

    def list_subject_students(
        self, subject_id: int, workspace_id: int, actor_membership
    ) -> list[dict]:
        subject = self._get_subject_or_404(subject_id, workspace_id)
        workspace = self.workspaces.get_by_id(workspace_id)
        actor_link = self.subject_memberships.find_active_by_role(
            actor_membership.id, subject_id, SubjectRole.TEACHER.value
        )

        if can_manage_subjects(workspace, actor_membership):
            pass
        elif verify_subject_teacher_access(actor_link):
            pass
        else:
            raise ForbiddenError(
                "Teachers may only list students for subjects they teach"
            )

        links = self.subject_memberships.list_students_for_subject(subject_id)
        return [self._serialize_assignment(link) for link in links]

    def get_actor_subject_link(
        self, membership_id: int, subject_id: int
    ) -> SubjectMembership | None:
        return self.subject_memberships.find_active(membership_id, subject_id)

    def _get_subject_or_404(self, subject_id: int, workspace_id: int) -> Subject:
        subject = self.subjects.get_active_by_id(subject_id, workspace_id)
        if not subject:
            raise NotFoundError("Subject not found")
        return subject

    def _ensure_can_view_subject(self, subject: Subject, actor_membership) -> None:
        workspace = self.workspaces.get_by_id(subject.workspace_id)
        if can_manage_subjects(workspace, actor_membership):
            return
        link = self.subject_memberships.find_active(actor_membership.id, subject.id)
        if link:
            return
        raise ForbiddenError("You do not have access to this subject")

    def _subjects_for_membership(
        self, membership_id: int, workspace_id: int
    ) -> list[Subject]:
        return list(
            db.session.execute(
                db.select(Subject)
                .join(
                    SubjectMembership,
                    SubjectMembership.subject_id == Subject.id,
                )
                .where(
                    SubjectMembership.membership_id == membership_id,
                    Subject.workspace_id == workspace_id,
                    Subject.deleted_at.is_(None),
                    SubjectMembership.deleted_at.is_(None),
                    SubjectMembership.status == SubjectMembershipStatus.ACTIVE.value,
                )
                .order_by(Subject.name)
            ).scalars().all()
        )

    def _serialize_subject(self, subject: Subject) -> dict:
        return {
            "id": subject.id,
            "name": subject.name,
            "title": subject.name,
            "code": subject.code,
            "description": subject.description,
            "workspace_id": subject.workspace_id,
            "is_archived": subject.is_archived,
            "created_by_membership_id": subject.created_by_membership_id,
            "created_at": subject.created_at.isoformat() if subject.created_at else None,
            "updated_at": subject.updated_at.isoformat() if subject.updated_at else None,
        }

    def _serialize_assignment(self, link: SubjectMembership) -> dict:
        membership = self.memberships.get_by_id(link.membership_id)
        return {
            "assignment_id": link.id,
            "membership_id": link.membership_id,
            "subject_id": link.subject_id,
            "subject_role": link.subject_role,
            "membership_role": membership.role if membership else None,
            "assigned_at": link.created_at.isoformat() if link.created_at else None,
        }
