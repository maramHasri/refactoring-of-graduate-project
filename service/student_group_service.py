"""
Student groups — manual student cohorts scoped to a subject.

Groups belong to one subject. Only subject teachers (or workspace admins) may manage them.
Membership is static: students must already be enrolled in the subject.
"""

from utils.messages import Messages
from models import StudentGroup, StudentGroupMember
from repositories.student_group_repository import StudentGroupRepository
from repositories.subject_repository import (
    SubjectMembershipRepository,
    SubjectRepository,
)
from repositories.workspace_repository import MembershipRepository, WorkspaceRepository
from service.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from utils.academic_rbac import can_manage_student_groups
from utils.db import db
from utils.enums import MembershipRole, MembershipStatus, SubjectRole


class StudentGroupService:
    def __init__(self):
        self.groups = StudentGroupRepository()
        self.subjects = SubjectRepository()
        self.subject_memberships = SubjectMembershipRepository()
        self.memberships = MembershipRepository()
        self.workspaces = WorkspaceRepository()

    def create_group(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        name: str,
        actor_membership,
        description: str | None = None,
    ) -> StudentGroup:
        subject = self._resolve_subject_for_manage(
            workspace_id=workspace_id,
            subject_id=subject_id,
            actor_membership=actor_membership,
        )
        name = name.strip()
        if not name:
            raise ValidationError(Messages.GROUP_NAME_IS_REQUIRED)

        if self.groups.find_by_subject_and_name(subject.id, name):
            raise ConflictError(Messages.A_GROUP_WITH_THIS_NAME_ALREADY_EXISTS_IN_THE_SUBJECT)

        group = StudentGroup(
            workspace_id=workspace_id,
            subject_id=subject.id,
            name=name,
            description=(description or "").strip() or None,
            created_by_membership_id=actor_membership.id,
        )
        self.groups.add(group)
        db.session.commit()
        return group

    def list_subject_groups(
        self, *, workspace_id: int, subject_id: int, actor_membership
    ) -> list[dict]:
        self._resolve_subject_for_manage(
            workspace_id=workspace_id,
            subject_id=subject_id,
            actor_membership=actor_membership,
        )
        rows = self.groups.list_by_subject(subject_id, workspace_id)
        counts = self.groups.count_members_for_groups([group.id for group in rows])
        return [
            self._serialize_group_list_item(group, counts.get(group.id, 0))
            for group in rows
        ]

    def get_group(
        self, *, workspace_id: int, group_id: int, actor_membership
    ) -> dict:
        group = self._get_group_or_404(group_id, workspace_id)
        self._ensure_can_manage_group(
            workspace_id=workspace_id,
            subject_id=group.subject_id,
            actor_membership=actor_membership,
        )
        return self._serialize_group_detail(group)

    def update_group(
        self,
        *,
        workspace_id: int,
        group_id: int,
        actor_membership,
        data: dict,
    ) -> StudentGroup:
        group = self._get_group_or_404(group_id, workspace_id)
        self._ensure_can_manage_group(
            workspace_id=workspace_id,
            subject_id=group.subject_id,
            actor_membership=actor_membership,
        )

        if "name" in data and data["name"] is not None:
            name = data["name"].strip()
            if not name:
                raise ValidationError(Messages.GROUP_NAME_IS_REQUIRED)
            existing = self.groups.find_by_subject_and_name(group.subject_id, name)
            if existing and existing.id != group.id:
                raise ConflictError(Messages.A_GROUP_WITH_THIS_NAME_ALREADY_EXISTS_IN_THE_SUBJECT)
            group.name = name

        if "description" in data:
            group.description = (data.get("description") or "").strip() or None

        db.session.commit()
        return group

    def delete_group(
        self, *, workspace_id: int, group_id: int, actor_membership
    ) -> None:
        group = self._get_group_or_404(group_id, workspace_id)
        self._ensure_can_manage_group(
            workspace_id=workspace_id,
            subject_id=group.subject_id,
            actor_membership=actor_membership,
        )
        self.groups.delete_group(group)
        db.session.commit()

    def add_members(
        self,
        *,
        workspace_id: int,
        group_id: int,
        student_ids: list[int],
        actor_membership,
    ) -> dict:
        group = self._get_group_or_404(group_id, workspace_id)
        self._ensure_can_manage_group(
            workspace_id=workspace_id,
            subject_id=group.subject_id,
            actor_membership=actor_membership,
        )

        unique_ids: list[int] = []
        seen: set[int] = set()
        skipped_from_request = 0
        for student_id in student_ids:
            if student_id in seen:
                skipped_from_request += 1
                continue
            seen.add(student_id)
            unique_ids.append(student_id)

        existing_member_ids = self.groups.list_member_ids(group.id)
        added_count = 0
        skipped_existing = 0

        for student_membership_id in unique_ids:
            if student_membership_id in existing_member_ids:
                skipped_existing += 1
                continue

            self._validate_subject_student(
                workspace_id=workspace_id,
                subject_id=group.subject_id,
                student_membership_id=student_membership_id,
            )
            self.groups.add(
                StudentGroupMember(
                    group_id=group.id,
                    student_membership_id=student_membership_id,
                )
            )
            added_count += 1

        db.session.commit()
        return {
            "added_count": added_count,
            "skipped_count": skipped_from_request + skipped_existing,
        }

    def remove_member(
        self,
        *,
        workspace_id: int,
        group_id: int,
        student_id: int,
        actor_membership,
    ) -> None:
        group = self._get_group_or_404(group_id, workspace_id)
        self._ensure_can_manage_group(
            workspace_id=workspace_id,
            subject_id=group.subject_id,
            actor_membership=actor_membership,
        )

        member = self.groups.find_member(
            group_id=group.id,
            student_membership_id=student_id,
        )
        if not member:
            raise NotFoundError(Messages.STUDENT_IS_NOT_A_MEMBER_OF_THIS_GROUP)

        db.session.delete(member)
        db.session.commit()

    def _resolve_subject_for_manage(
        self, *, workspace_id: int, subject_id: int, actor_membership
    ):
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)

        subject = self.subjects.get_active_by_id(subject_id, workspace_id)
        if not subject:
            raise NotFoundError(Messages.SUBJECT_NOT_FOUND)

        self._ensure_can_manage_group(
            workspace_id=workspace_id,
            subject_id=subject_id,
            actor_membership=actor_membership,
            workspace=workspace,
        )
        return subject

    def _ensure_can_manage_group(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        actor_membership,
        workspace=None,
    ) -> None:
        workspace = workspace or self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)

        actor_link = self.subject_memberships.find_active_by_role(
            actor_membership.id, subject_id, SubjectRole.TEACHER.value
        )
        if not can_manage_student_groups(workspace, actor_membership, actor_link):
            raise ForbiddenError(Messages.ONLY_SUBJECT_TEACHERS_OR_WORKSPACE_ADMINS_CAN_MANAGE_STUDENT_GROUPS)

    def _get_group_or_404(self, group_id: int, workspace_id: int) -> StudentGroup:
        group = self.groups.get_in_workspace(group_id, workspace_id)
        if not group:
            raise NotFoundError(Messages.GROUP_NOT_FOUND)
        return group

    def _validate_subject_student(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        student_membership_id: int,
    ) -> None:
        membership = self.memberships.get_by_id(student_membership_id)
        if not membership or membership.workspace_id != workspace_id:
            raise ValidationError(Messages.STUDENT_STUDENT_MEMBERSHIP_ID_IS_NOT_A_MEMBER_OF_THIS_WORKSPACE.format(student_membership_id=student_membership_id))
        if membership.role != MembershipRole.STUDENT.value:
            raise ValidationError(Messages.MEMBERSHIP_STUDENT_MEMBERSHIP_ID_IS_NOT_A_STUDENT.format(student_membership_id=student_membership_id))
        if membership.status != MembershipStatus.ACTIVE.value:
            raise ValidationError(Messages.STUDENT_STUDENT_MEMBERSHIP_ID_IS_NOT_AN_ACTIVE_WORKSPACE_MEMBER.format(student_membership_id=student_membership_id))

        enrollment = self.subject_memberships.find_active_by_role(
            student_membership_id, subject_id, SubjectRole.STUDENT.value
        )
        if not enrollment:
            raise ValidationError(Messages.STUDENT_STUDENT_MEMBERSHIP_ID_IS_NOT_ENROLLED_IN_THIS_SUBJECT.format(student_membership_id=student_membership_id))

    def _serialize_group_list_item(self, group: StudentGroup, student_count: int) -> dict:
        return {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "student_count": student_count,
            "created_at": group.created_at.isoformat() if group.created_at else None,
        }

    def _serialize_group(self, group: StudentGroup) -> dict:
        return {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "subject_id": group.subject_id,
            "workspace_id": group.workspace_id,
            "created_by_membership_id": group.created_by_membership_id,
            "created_at": group.created_at.isoformat() if group.created_at else None,
            "updated_at": group.updated_at.isoformat() if group.updated_at else None,
        }

    def _serialize_group_detail(self, group: StudentGroup) -> dict:
        subject = group.subject or self.subjects.get_by_id(group.subject_id)
        member_rows = self.groups.list_members_with_users(group.id)
        students = [
            {
                "id": membership.id,
                "user_id": membership.user_id,
                "full_name": user.full_name if user else None,
                "email": user.email if user else None,
            }
            for _member, membership, user in member_rows
        ]
        return {
            **self._serialize_group(group),
            "subject": {
                "id": subject.id if subject else group.subject_id,
                "name": subject.name if subject else None,
            },
            "member_count": len(students),
            "students": students,
        }
