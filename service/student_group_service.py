"""
Student groups — teacher-owned cohorts within a subject.

Rules:
- Only assigned subject teachers create groups (not institution admin).
- Teachers manage only groups they own (created_by_membership_id).
- Workspace owner/admin may view all groups in a subject.
- A student may belong to at most one group per subject (across all teachers).
- Hard delete only; removing a member frees them for another group immediately.
"""

from __future__ import annotations

from utils.messages import Messages
from models import StudentGroup, StudentGroupMember
from repositories.student_group_repository import StudentGroupRepository
from repositories.subject_repository import (
    SubjectMembershipRepository,
    SubjectRepository,
)
from repositories.workspace_repository import MembershipRepository, WorkspaceRepository
from service.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    StudentGroupSubjectConflictError,
    ValidationError,
)
from utils.academic_rbac import (
    can_create_subject_student_group,
    can_manage_subjects,
    can_view_subject_student_groups,
    verify_subject_teacher_access,
)
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
        subject = self._resolve_subject_for_create(
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
        workspace, _subject, actor_link = self._resolve_subject_for_view(
            workspace_id=workspace_id,
            subject_id=subject_id,
            actor_membership=actor_membership,
        )
        if can_manage_subjects(workspace, actor_membership):
            rows = self.groups.list_by_subject(subject_id, workspace_id)
        else:
            rows = self.groups.list_by_subject_for_owner(
                subject_id, workspace_id, actor_membership.id
            )
        counts = self.groups.count_members_for_groups([group.id for group in rows])
        return [
            self._serialize_group_list_item(group, counts.get(group.id, 0))
            for group in rows
        ]

    def list_workspace_groups(
        self, *, workspace_id: int, actor_membership
    ) -> list[dict]:
        """
        Workspace-wide student groups overview.

        Owner/ADMIN: all groups in the workspace.
        TEACHER: only groups they own (across subjects).
        """
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)

        if can_manage_subjects(workspace, actor_membership):
            rows = self.groups.list_by_workspace(workspace_id)
        elif actor_membership.role == MembershipRole.TEACHER.value:
            rows = self.groups.list_by_workspace_for_owner(
                workspace_id, actor_membership.id
            )
        else:
            raise ForbiddenError(
                Messages.ONLY_SUBJECT_TEACHERS_OR_WORKSPACE_ADMINS_CAN_MANAGE_STUDENT_GROUPS
            )

        members_map = self.groups.map_members_with_users_for_groups(
            [group.id for group in rows]
        )
        return [
            self._serialize_workspace_group_item(
                group, members_map.get(group.id, [])
            )
            for group in rows
        ]

    def list_available_students(
        self, *, workspace_id: int, subject_id: int, actor_membership
    ) -> list[dict]:
        self._resolve_subject_for_view(
            workspace_id=workspace_id,
            subject_id=subject_id,
            actor_membership=actor_membership,
        )
        enrollments = self.subject_memberships.list_students_for_subject(subject_id)
        student_ids = [link.membership_id for link in enrollments]
        current_groups = self.groups.map_current_groups_for_students_in_subject(
            subject_id=subject_id,
            student_membership_ids=student_ids,
        )

        items: list[dict] = []
        for link in enrollments:
            membership = link.membership or self.memberships.get_by_id(link.membership_id)
            if not membership:
                continue
            user = membership.user
            group = current_groups.get(membership.id)
            items.append(
                {
                    "membership_id": membership.id,
                    "name": user.full_name if user else None,
                    "full_name": user.full_name if user else None,
                    "email": user.email if user else None,
                    "is_available": group is None,
                    "current_group": self._serialize_current_group(group)
                    if group
                    else None,
                }
            )
        items.sort(key=lambda row: ((row.get("name") or "").lower(), row["membership_id"]))
        return items

    def get_group(
        self, *, workspace_id: int, group_id: int, actor_membership
    ) -> dict:
        group = self._get_group_or_404(group_id, workspace_id)
        self._ensure_can_view_group(
            workspace_id=workspace_id,
            group=group,
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
        self._ensure_is_group_owner(group, actor_membership)

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
        self._ensure_is_group_owner(group, actor_membership)
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
        self._ensure_is_group_owner(group, actor_membership)

        unique_ids: list[int] = []
        seen: set[int] = set()
        for student_id in student_ids:
            if student_id in seen:
                continue
            seen.add(student_id)
            unique_ids.append(student_id)

        existing_member_ids = self.groups.list_member_ids(group.id)
        to_add = [sid for sid in unique_ids if sid not in existing_member_ids]

        for student_membership_id in to_add:
            self._validate_subject_student(
                workspace_id=workspace_id,
                subject_id=group.subject_id,
                student_membership_id=student_membership_id,
            )

        conflicts_map = self.groups.map_current_groups_for_students_in_subject(
            subject_id=group.subject_id,
            student_membership_ids=to_add,
            exclude_group_id=group.id,
        )
        if conflicts_map:
            conflicts = [
                self._build_conflict_item(membership_id, other_group)
                for membership_id, other_group in sorted(conflicts_map.items())
            ]
            raise StudentGroupSubjectConflictError(conflicts)

        for student_membership_id in to_add:
            self.groups.add(
                StudentGroupMember(
                    group_id=group.id,
                    student_membership_id=student_membership_id,
                )
            )

        db.session.commit()
        return {
            "added_count": len(to_add),
            "skipped_count": len(unique_ids) - len(to_add),
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
        self._ensure_is_group_owner(group, actor_membership)

        member = self.groups.find_member(
            group_id=group.id,
            student_membership_id=student_id,
        )
        if not member:
            raise NotFoundError(Messages.STUDENT_IS_NOT_A_MEMBER_OF_THIS_GROUP)

        db.session.delete(member)
        db.session.commit()

    def _resolve_subject_for_create(
        self, *, workspace_id: int, subject_id: int, actor_membership
    ):
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)
        subject = self.subjects.get_active_by_id(subject_id, workspace_id)
        if not subject:
            raise NotFoundError(Messages.SUBJECT_NOT_FOUND)

        actor_link = self.subject_memberships.find_active_by_role(
            actor_membership.id, subject_id, SubjectRole.TEACHER.value
        )
        if not can_create_subject_student_group(workspace, actor_link):
            raise ForbiddenError(Messages.ONLY_ASSIGNED_SUBJECT_TEACHERS_CAN_CREATE_STUDENT_GROUPS)
        return subject

    def _resolve_subject_for_view(
        self, *, workspace_id: int, subject_id: int, actor_membership
    ):
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)
        subject = self.subjects.get_active_by_id(subject_id, workspace_id)
        if not subject:
            raise NotFoundError(Messages.SUBJECT_NOT_FOUND)

        actor_link = self.subject_memberships.find_active_by_role(
            actor_membership.id, subject_id, SubjectRole.TEACHER.value
        )
        if not can_view_subject_student_groups(workspace, actor_membership, actor_link):
            raise ForbiddenError(
                Messages.ONLY_SUBJECT_TEACHERS_OR_WORKSPACE_ADMINS_CAN_MANAGE_STUDENT_GROUPS
            )
        return workspace, subject, actor_link

    def _ensure_can_view_group(
        self, *, workspace_id: int, group: StudentGroup, actor_membership
    ) -> None:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)
        if can_manage_subjects(workspace, actor_membership):
            return
        actor_link = self.subject_memberships.find_active_by_role(
            actor_membership.id, group.subject_id, SubjectRole.TEACHER.value
        )
        if not verify_subject_teacher_access(actor_link):
            raise ForbiddenError(
                Messages.ONLY_SUBJECT_TEACHERS_OR_WORKSPACE_ADMINS_CAN_MANAGE_STUDENT_GROUPS
            )
        if group.created_by_membership_id != actor_membership.id:
            raise ForbiddenError(Messages.ONLY_THE_GROUP_OWNER_CAN_MANAGE_THIS_STUDENT_GROUP)

    def _ensure_is_group_owner(self, group: StudentGroup, actor_membership) -> None:
        actor_link = self.subject_memberships.find_active_by_role(
            actor_membership.id, group.subject_id, SubjectRole.TEACHER.value
        )
        if not verify_subject_teacher_access(actor_link):
            raise ForbiddenError(Messages.ONLY_THE_GROUP_OWNER_CAN_MANAGE_THIS_STUDENT_GROUP)
        if group.created_by_membership_id != actor_membership.id:
            raise ForbiddenError(Messages.ONLY_THE_GROUP_OWNER_CAN_MANAGE_THIS_STUDENT_GROUP)

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
            raise ValidationError(
                Messages.STUDENT_STUDENT_MEMBERSHIP_ID_IS_NOT_A_MEMBER_OF_THIS_WORKSPACE.format(
                    student_membership_id=student_membership_id
                )
            )
        if membership.role != MembershipRole.STUDENT.value:
            raise ValidationError(
                Messages.MEMBERSHIP_STUDENT_MEMBERSHIP_ID_IS_NOT_A_STUDENT.format(
                    student_membership_id=student_membership_id
                )
            )
        if membership.status != MembershipStatus.ACTIVE.value:
            raise ValidationError(
                Messages.STUDENT_STUDENT_MEMBERSHIP_ID_IS_NOT_AN_ACTIVE_WORKSPACE_MEMBER.format(
                    student_membership_id=student_membership_id
                )
            )

        enrollment = self.subject_memberships.find_active_by_role(
            student_membership_id, subject_id, SubjectRole.STUDENT.value
        )
        if not enrollment:
            raise ValidationError(
                Messages.STUDENT_STUDENT_MEMBERSHIP_ID_IS_NOT_ENROLLED_IN_THIS_SUBJECT.format(
                    student_membership_id=student_membership_id
                )
            )

    def _build_conflict_item(self, membership_id: int, group: StudentGroup) -> dict:
        membership = self.memberships.get_by_id(membership_id)
        user = membership.user if membership else None
        owner = group.created_by
        owner_user = owner.user if owner else None
        return {
            "membership_id": membership_id,
            "student_name": user.full_name if user else None,
            "existing_group_id": group.id,
            "existing_group_name": group.name,
            "existing_group_owner": owner_user.full_name if owner_user else None,
            "existing_group_owner_membership_id": group.created_by_membership_id,
        }

    def _serialize_current_group(self, group: StudentGroup) -> dict:
        owner = group.created_by
        owner_user = owner.user if owner else None
        return {
            "id": group.id,
            "name": group.name,
            "owner_membership_id": group.created_by_membership_id,
            "owner_name": owner_user.full_name if owner_user else None,
        }

    def _serialize_group_list_item(self, group: StudentGroup, student_count: int) -> dict:
        owner = group.created_by
        owner_user = owner.user if owner else None
        return {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "student_count": student_count,
            "created_by_membership_id": group.created_by_membership_id,
            "owner_name": owner_user.full_name if owner_user else None,
            "created_at": group.created_at.isoformat() if group.created_at else None,
        }

    def _serialize_group_students(
        self,
        member_rows: list[tuple[StudentGroupMember, object, object]],
    ) -> list[dict]:
        return [
            {
                "id": membership.id,
                "membership_id": membership.id,
                "user_id": membership.user_id,
                "full_name": user.full_name if user else None,
                "email": user.email if user else None,
            }
            for _member, membership, user in member_rows
        ]

    def _serialize_workspace_group_item(
        self,
        group: StudentGroup,
        member_rows: list[tuple[StudentGroupMember, object, object]],
    ) -> dict:
        subject = group.subject
        owner = group.created_by
        owner_user = owner.user if owner else None
        students = self._serialize_group_students(member_rows)
        return {
            **self._serialize_group(group),
            "owner_name": owner_user.full_name if owner_user else None,
            "subject": {
                "id": subject.id if subject else group.subject_id,
                "name": subject.name if subject else None,
            },
            "member_count": len(students),
            "student_count": len(students),
            "students": students,
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
        students = self._serialize_group_students(member_rows)
        owner = group.created_by
        owner_user = owner.user if owner else None
        return {
            **self._serialize_group(group),
            "owner_name": owner_user.full_name if owner_user else None,
            "subject": {
                "id": subject.id if subject else group.subject_id,
                "name": subject.name if subject else None,
            },
            "member_count": len(students),
            "students": students,
        }
