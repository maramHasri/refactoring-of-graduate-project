"""
Workspace business logic.

Owner vs admin:
- owner_membership_id identifies the privileged admin (owner is NOT a separate role).
- Owner can delete workspace, transfer ownership, remove admins.
- Regular admins cannot remove other admins.
"""

from utils.messages import Messages
import re
from datetime import datetime, timedelta

from models import Membership, Test, TestAttempt, Workspace, WorkspaceProfile
from repositories.attempt_repository import TestAttemptRepository
from repositories.question_bank_repository import QuestionBankRepository
from repositories.student_group_repository import StudentGroupRepository
from repositories.subject_repository import SubjectMembershipRepository
from repositories.test_assignment_repository import TestStudentAssignmentRepository
from repositories.test_repository import TestRepository
from repositories.user_repository import UserRepository
from repositories.workspace_repository import MembershipRepository, WorkspaceRepository
from service.attempt_service import AttemptService
from service.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from service.user_service import UserService
from utils.app_timezone import ensure_local_aware, format_local_datetime, local_timezone_now
from utils.db import db
from utils.rbac import (
    can_list_institution_workspace_teachers,
    can_list_workspace_students,
    can_manage_workspace_members,
    is_workspace_owner,
)
from utils.enums import (
    AvailabilityTimeMode,
    MembershipRole,
    SubjectRole,
    WorkspaceKind,
    WorkspaceStatus,
)
from utils.join_code import generate_workspace_join_code
from utils.pagination import build_pagination_meta, normalize_pagination


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:100] or "workspace"


class WorkspaceService:
    def __init__(self):
        self.workspaces = WorkspaceRepository()
        self.memberships = MembershipRepository()
        self.subject_memberships = SubjectMembershipRepository()
        self.student_groups = StudentGroupRepository()
        self.test_assignments = TestStudentAssignmentRepository()
        self.test_attempts = TestAttemptRepository()
        self.tests = TestRepository()
        self.question_banks = QuestionBankRepository()
        self.user_repo = UserRepository()
        self.user_service = UserService()
        self.attempt_service = AttemptService()

    def get_workspace_member_details(
        self,
        workspace_id: int,
        actor_membership: Membership,
        membership_id: int,
    ) -> dict:
        """
        GET /workspaces/members/{membership_id} — student or teacher detail.
        Works for INSTITUTION and SOLO workspaces (owner or ADMIN).
        """
        workspace = self._ensure_can_manage_workspace_members(
            workspace_id, actor_membership
        )
        row = self.memberships.get_with_user(membership_id)
        if not row:
            raise NotFoundError(Messages.MEMBERSHIP_NOT_FOUND_IN_THIS_WORKSPACE)
        target, user = row
        if target.workspace_id != workspace.id:
            raise NotFoundError(Messages.MEMBERSHIP_NOT_FOUND_IN_THIS_WORKSPACE)
        if target.role not in (
            MembershipRole.STUDENT.value,
            MembershipRole.TEACHER.value,
        ):
            raise ValidationError(Messages.MEMBER_DETAILS_ARE_ONLY_AVAILABLE_FOR_STUDENTS_AND_TEACHERS)

        last_activity_at = self._resolve_member_last_activity_at(user, workspace.id)
        subjects = self._serialize_member_subjects(target, workspace.id)

        if target.role == MembershipRole.STUDENT.value:
            upcoming_raw = self.attempt_service.list_upcoming_tests(
                workspace_id=workspace.id,
                actor_membership=target,
            )
            test_ids = [item["test_id"] for item in upcoming_raw]
            tests_by_id = self._fetch_tests_by_ids(test_ids)
            return {
                "student": self._serialize_member_identity(
                    user, target, last_activity_at
                ),
                "subjects": subjects,
                "upcoming_tests": [
                    self._serialize_member_upcoming_test(
                        item, tests_by_id.get(item["test_id"])
                    )
                    for item in upcoming_raw
                ],
                "completed_tests": [
                    self._serialize_member_completed_test(attempt)
                    for attempt in self.test_attempts.list_completed_for_student(
                        workspace_id=workspace.id,
                        student_membership_id=target.id,
                        student_user_id=user.id,
                    )
                ],
            }

        return {
            "teacher": self._serialize_member_identity(user, target, last_activity_at),
            "subjects": subjects,
            "statistics": {
                "question_banks_created": self.question_banks.count_by_creator(
                    target.id, workspace.id
                ),
                "tests_created": self.tests.count_for_creator(target.id),
            },
        }

    def list_recently_active_members(
        self,
        workspace_id: int,
        actor_membership: Membership,
        *,
        role: str | None = None,
    ) -> dict:
        """
        GET /workspaces/members/recently-active — members active in the last 24 hours.
        Works for INSTITUTION and SOLO workspaces (owner or ADMIN).
        """
        self._ensure_can_manage_workspace_members(workspace_id, actor_membership)
        since = local_timezone_now() - timedelta(hours=24)
        rows = self.memberships.list_recently_active_in_workspace(
            workspace_id,
            since=since,
            role=role,
        )
        if role is None:
            rows = [
                row
                for row in rows
                if row[0].role
                in (MembershipRole.STUDENT.value, MembershipRole.TEACHER.value)
            ]

        return {
            "members": [
                self._serialize_recently_active_member(
                    membership, user, activity_at
                )
                for membership, user, activity_at in rows
            ]
        }

    def update_workspace_member(
        self,
        workspace_id: int,
        actor_membership: Membership,
        membership_id: int,
        data: dict,
    ) -> dict:
        """
        PATCH /workspaces/members/{membership_id} — update linked User profile fields.
        Does not modify membership role, workspace, or relationship fields.
        """
        workspace = self._ensure_can_manage_workspace_members(
            workspace_id, actor_membership
        )

        target = self.memberships.get_by_id(membership_id)
        if not target or target.workspace_id != workspace.id:
            raise NotFoundError(Messages.MEMBERSHIP_NOT_FOUND_IN_THIS_WORKSPACE)
        if target.status != "ACTIVE":
            raise ValidationError(Messages.MEMBERSHIP_IS_NOT_ACTIVE)

        user = self.user_repo.get_by_id(target.user_id)
        if not user:
            raise NotFoundError(Messages.USER_NOT_FOUND)

        self.user_service.update_profile(user, data)

        subject_count, subject_count_field = self._member_subject_count(
            workspace.id, target
        )
        member = self._serialize_workspace_member(
            target,
            user,
            subject_count=subject_count,
            subject_count_field=subject_count_field,
        )
        return {
            "message": Messages.WORKSPACE_MEMBER_UPDATED_SUCCESSFULLY,
            "member": member,
        }

    def create_workspace(
        self,
        *,
        user_id: int,
        name: str,
        kind: str,
        slug: str | None = None,
        logo_url: str | None = None,
        description: str | None = None,
    ) -> dict:
        """
        Purpose: Authenticated user creates a new workspace (owner onboarding).
        Side effects: workspace, ADMIN membership, owner_membership_id, join_code.
        """
        if kind not in (WorkspaceKind.SOLO.value, WorkspaceKind.INSTITUTION.value):
            raise ValidationError(Messages.INVALID_WORKSPACE_KIND)

        slug = slug or _slugify(name)
        if self.workspaces.find_by_slug(slug):
            raise ConflictError(Messages.WORKSPACE_SLUG_ALREADY_EXISTS)

        workspace = Workspace(
            name=name,
            slug=slug,
            kind=kind,
            owner_user_id=user_id,
            join_code=self._unique_join_code(),
            logo_url=(logo_url or "").strip() or None,
        )
        self.workspaces.add(workspace)
        db.session.flush()

        membership = Membership(
            user_id=user_id,
            workspace_id=workspace.id,
            role=MembershipRole.ADMIN.value,
            status="ACTIVE",
        )
        self.memberships.add(membership)
        db.session.flush()

        workspace.owner_membership_id = membership.id

        description_value = (description or "").strip() or None
        if description_value:
            self._set_workspace_description(workspace, description_value)

        db.session.commit()

        return {
            "workspace_id": workspace.id,
            "membership_id": membership.id,
            "join_code": workspace.join_code,
        }

    def list_institution_workspace_teachers(
        self,
        workspace_id: int,
        actor_membership: Membership,
        *,
        page: int | None = None,
        per_page: int | None = None,
        search: str | None = None,
    ) -> dict:
        """
        GET /workspaces/teachers — active TEACHER memberships in the institution workspace.
        Caller must be institution owner or workspace ADMIN (X-Workspace-Id context).
        """
        result = self._list_institution_workspace_members(
            workspace_id,
            actor_membership,
            role=MembershipRole.TEACHER.value,
            subject_role=SubjectRole.TEACHER.value,
            subject_count_field="assigned_subjects_count",
            page=page,
            per_page=per_page,
            search=search,
        )
        items = result["items"]
        return {
            "success": True,
            "teachers": items,
            "data": items,
            "count": result["count"],
            **result["pagination"],
        }

    def list_institution_workspace_students(
        self,
        workspace_id: int,
        actor_membership: Membership,
        *,
        page: int | None = None,
        per_page: int | None = None,
        search: str | None = None,
    ) -> dict:
        """
        GET /workspaces/students — students in the active workspace.

        INSTITUTION: all active STUDENT workspace memberships.
        SOLO: students enrolled in at least one subject in this workspace.
        """
        workspace = self._get_workspace_or_404(workspace_id)
        self._ensure_workspace_student_list_access(workspace, actor_membership)

        enrolled_only = workspace.kind == WorkspaceKind.SOLO.value
        result = self._list_workspace_students(
            workspace_id,
            page=page,
            per_page=per_page,
            search=search,
            enrolled_in_subjects_only=enrolled_only,
        )
        items = result["items"]
        return {
            "success": True,
            "students": items,
            "count": result["count"],
            **result["pagination"],
        }

    def list_institution_workspace_tests(
        self,
        workspace_id: int,
        actor_membership: Membership,
        *,
        page: int | None = None,
        per_page: int | None = None,
        status: str | None = None,
    ) -> dict:
        """
        GET /workspaces/tests — all exams created in an institution workspace.

        Institution workspace owner only. Includes tests created by any teacher
        (or other creator membership) inside this workspace.
        """
        workspace = self._get_workspace_or_404(workspace_id)
        if workspace.kind != WorkspaceKind.INSTITUTION.value:
            raise ForbiddenError(
                Messages.THIS_ENDPOINT_IS_ONLY_AVAILABLE_FOR_INSTITUTION_WORKSPACES
            )
        if not is_workspace_owner(workspace, actor_membership):
            raise ForbiddenError(
                Messages.ONLY_THE_WORKSPACE_OWNER_CAN_LIST_INSTITUTION_TESTS
            )

        page, per_page, offset = normalize_pagination(page, per_page)
        rows, total = self.tests.list_for_workspace(
            workspace_id,
            status=status,
            offset=offset,
            limit=per_page,
        )
        items = [self._serialize_institution_workspace_test(test) for test in rows]
        return {
            "success": True,
            "tests": items,
            "count": len(items),
            **build_pagination_meta(total=total, page=page, per_page=per_page),
        }

    def remove_teacher_from_workspace(
        self,
        workspace_id: int,
        actor_membership: Membership,
        membership_id: int,
    ) -> dict:
        """
        DELETE /workspaces/teachers?membership_id= — remove teacher from institution workspace.
        Cleans up subject teacher assignments in this workspace, then deletes the membership.
        """
        workspace = self._ensure_institution_admin_member_list_access(
            workspace_id, actor_membership
        )
        target = self._get_removable_workspace_member(
            workspace,
            membership_id,
            expected_role=MembershipRole.TEACHER.value,
        )
        self._cleanup_teacher_workspace_relationships(membership_id, workspace_id)
        db.session.delete(target)
        db.session.commit()
        return {"message": Messages.TEACHER_REMOVED_FROM_WORKSPACE_SUCCESSFULLY}

    def remove_student_from_workspace(
        self,
        workspace_id: int,
        actor_membership: Membership,
        membership_id: int,
    ) -> dict:
        """
        DELETE /workspaces/students?membership_id= — remove student from active workspace.
        Cleans up enrollments, groups, and test assignments in this workspace, then membership.
        """
        workspace = self._get_workspace_or_404(workspace_id)
        self._ensure_workspace_student_list_access(workspace, actor_membership)
        target = self._get_removable_workspace_member(
            workspace,
            membership_id,
            expected_role=MembershipRole.STUDENT.value,
        )
        self._cleanup_student_workspace_relationships(membership_id, workspace_id)
        db.session.delete(target)
        db.session.commit()
        return {"message": Messages.STUDENT_REMOVED_FROM_WORKSPACE_SUCCESSFULLY}

    def _get_removable_workspace_member(
        self,
        workspace: Workspace,
        membership_id: int,
        *,
        expected_role: str,
    ) -> Membership:
        target = self.memberships.get_by_id(membership_id)
        if not target or target.workspace_id != workspace.id:
            raise NotFoundError(Messages.MEMBERSHIP_NOT_FOUND_IN_THIS_WORKSPACE)
        if target.status != "ACTIVE":
            raise ValidationError(Messages.MEMBERSHIP_IS_NOT_ACTIVE)
        if target.role != expected_role:
            raise ValidationError(
                Messages.MEMBERSHIP_IS_NOT_A_WORKSPACE_ROLE.format(role=expected_role.lower())
            )
        if workspace.owner_membership_id == target.id:
            raise ForbiddenError(Messages.CANNOT_REMOVE_THE_WORKSPACE_OWNER)
        return target

    def _cleanup_teacher_workspace_relationships(
        self, membership_id: int, workspace_id: int
    ) -> None:
        links = self.subject_memberships.list_teacher_assignments_for_membership(
            membership_id, workspace_id
        )
        for link in links:
            self.subject_memberships.soft_remove(link)

    def _cleanup_student_workspace_relationships(
        self, membership_id: int, workspace_id: int
    ) -> None:
        enrollments = self.subject_memberships.list_student_assignments_for_membership(
            membership_id, workspace_id
        )
        for link in enrollments:
            self.subject_memberships.soft_remove(link)

        self.student_groups.delete_members_for_student_in_workspace(
            membership_id, workspace_id
        )
        self.test_assignments.delete_for_student_in_workspace(
            membership_id, workspace_id
        )
        self.test_attempts.delete_for_student_in_workspace(
            membership_id, workspace_id
        )

    def _list_workspace_students(
        self,
        workspace_id: int,
        *,
        page: int | None = None,
        per_page: int | None = None,
        search: str | None = None,
        enrolled_in_subjects_only: bool = False,
    ) -> dict:
        page, per_page, offset = normalize_pagination(page, per_page)
        search_term = (search or "").strip() or None

        rows, total = self.memberships.list_active_members_by_role_with_subject_counts(
            workspace_id,
            MembershipRole.STUDENT.value,
            subject_role=SubjectRole.STUDENT.value,
            search=search_term,
            offset=offset,
            limit=per_page,
            enrolled_in_subjects_only=enrolled_in_subjects_only,
        )
        items = [
            self._serialize_workspace_member(
                membership,
                user,
                subject_count=subject_count,
                subject_count_field="enrolled_subjects_count",
            )
            for membership, user, subject_count in rows
        ]
        return {
            "items": items,
            "count": len(items),
            "pagination": build_pagination_meta(
                total=total, page=page, per_page=per_page
            ),
        }

    def _list_institution_workspace_members(
        self,
        workspace_id: int,
        actor_membership: Membership,
        *,
        role: str,
        subject_role: str,
        subject_count_field: str,
        page: int | None = None,
        per_page: int | None = None,
        search: str | None = None,
    ) -> dict:
        self._ensure_institution_admin_member_list_access(
            workspace_id, actor_membership
        )
        page, per_page, offset = normalize_pagination(page, per_page)
        search_term = (search or "").strip() or None

        rows, total = self.memberships.list_active_members_by_role_with_subject_counts(
            workspace_id,
            role,
            subject_role=subject_role,
            search=search_term,
            offset=offset,
            limit=per_page,
        )
        items = [
            self._serialize_workspace_member(
                membership,
                user,
                subject_count=subject_count,
                subject_count_field=subject_count_field,
            )
            for membership, user, subject_count in rows
        ]
        return {
            "items": items,
            "count": len(items),
            "pagination": build_pagination_meta(
                total=total, page=page, per_page=per_page
            ),
        }

    def _ensure_institution_admin_member_list_access(
        self, workspace_id: int, actor_membership: Membership
    ) -> Workspace:
        workspace = self._get_workspace_or_404(workspace_id)
        if workspace.kind != WorkspaceKind.INSTITUTION.value:
            raise ForbiddenError(Messages.THIS_ENDPOINT_IS_ONLY_AVAILABLE_FOR_INSTITUTION_WORKSPACES)
        if not can_list_institution_workspace_teachers(workspace, actor_membership):
            raise ForbiddenError(Messages.ONLY_THE_INSTITUTION_OWNER_OR_WORKSPACE_ADMIN_CAN_LIST_WORKSPACE_MEMBERS)
        return workspace

    def _ensure_can_manage_workspace_members(
        self, workspace_id: int, actor_membership: Membership
    ) -> Workspace:
        """
        Owner or ADMIN may manage members in INSTITUTION and SOLO workspaces.
        Workspace-type agnostic: SOLO owner is treated as the workspace administrator.
        """
        workspace = self._get_workspace_or_404(workspace_id)
        if workspace.kind not in (
            WorkspaceKind.INSTITUTION.value,
            WorkspaceKind.SOLO.value,
        ):
            raise ForbiddenError(Messages.UNSUPPORTED_WORKSPACE_TYPE_FOR_MEMBER_MANAGEMENT)
        if not can_manage_workspace_members(workspace, actor_membership):
            raise ForbiddenError(Messages.ONLY_THE_WORKSPACE_OWNER_OR_ADMIN_CAN_MANAGE_WORKSPACE_MEMBERS)
        return workspace

    def _ensure_workspace_student_list_access(
        self, workspace: Workspace, actor_membership: Membership
    ) -> None:
        if workspace.kind not in (
            WorkspaceKind.INSTITUTION.value,
            WorkspaceKind.SOLO.value,
        ):
            raise ForbiddenError(Messages.UNSUPPORTED_WORKSPACE_TYPE_FOR_STUDENT_LISTING)

        if not can_list_workspace_students(workspace, actor_membership):
            raise ForbiddenError(Messages.ONLY_THE_WORKSPACE_OWNER_OR_ADMIN_CAN_LIST_STUDENTS)

    def _get_workspace_or_404(self, workspace_id: int) -> Workspace:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)
        return workspace

    def list_accessible_workspaces(self, user_id: int, *, is_superadmin: bool) -> list[dict]:
        """
        Purpose: Return workspaces after login for workspace picker.
        Must NOT: mutate state.
        """
        if is_superadmin:
            rows = db.session.execute(db.select(Workspace).order_by(Workspace.name)).scalars().all()
            return [self._serialize_workspace(w, role="SUPERADMIN", membership_id=None) for w in rows]

        workspaces = self.workspaces.list_for_user(user_id)
        result = []
        for ws in workspaces:
            m = self.memberships.find_by_user_and_workspace(user_id, ws.id)
            result.append(
                self._serialize_workspace(
                    ws,
                    role=m.role if m else None,
                    membership_id=m.id if m else None,
                )
            )
        return result

    def get_workspace(self, workspace_id: int, actor_user_id: int, *, is_superadmin: bool) -> dict:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)
        if not is_superadmin:
            m = self.memberships.find_by_user_and_workspace(actor_user_id, workspace_id)
            if not m or m.status != "ACTIVE":
                raise ForbiddenError(Messages.NOT_A_MEMBER_OF_THIS_WORKSPACE)
            if workspace.status != WorkspaceStatus.ACTIVE.value:
                raise ForbiddenError(Messages.WORKSPACE_IS_NOT_ACTIVE)
        return self._serialize_workspace_detail(workspace)

    def update_workspace(
        self,
        workspace_id: int,
        actor_user_id: int,
        *,
        is_superadmin: bool,
        data: dict,
    ) -> Workspace:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)

        if not is_superadmin:
            m = self.memberships.find_by_user_and_workspace(actor_user_id, workspace_id)
            if not m or m.role not in (
                MembershipRole.ADMIN.value,
            ):
                raise ForbiddenError(Messages.ADMIN_ACCESS_REQUIRED)

        for field in ("name", "slug", "status", "subject_assignment_mode"):
            if field in data and data[field] is not None:
                setattr(workspace, field, data[field])

        if "logo_url" in data:
            workspace.logo_url = (data.get("logo_url") or "").strip() or None

        if "description" in data:
            self._set_workspace_description(
                workspace,
                (data.get("description") or "").strip() or None,
            )

        if "slug" in data and data["slug"]:
            existing = self.workspaces.find_by_slug(data["slug"])
            if existing and existing.id != workspace.id:
                raise ConflictError(Messages.SLUG_ALREADY_IN_USE)

        db.session.commit()
        return workspace

    def delete_workspace(
        self, workspace_id: int, actor_user_id: int, *, is_superadmin: bool
    ) -> None:
        """
        Purpose: Delete workspace.
        Only owner membership or super admin.
        """
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)

        if not is_superadmin:
            m = self.memberships.find_by_user_and_workspace(actor_user_id, workspace_id)
            if not m or workspace.owner_membership_id != m.id:
                raise ForbiddenError(Messages.ONLY_THE_WORKSPACE_OWNER_CAN_DELETE_THIS_WORKSPACE)

        db.session.delete(workspace)
        db.session.commit()

    def is_workspace_owner(self, workspace: Workspace, membership_id: int | None) -> bool:
        return membership_id is not None and workspace.owner_membership_id == membership_id

    def can_invite_teachers(self, workspace: Workspace) -> bool:
        return workspace.kind == WorkspaceKind.INSTITUTION.value

    def _unique_join_code(self) -> str:
        for _ in range(10):
            code = generate_workspace_join_code()
            if not self.workspaces.find_by_join_code(code):
                return code
        raise ConflictError(Messages.COULD_NOT_GENERATE_UNIQUE_JOIN_CODE)

    def _set_workspace_description(
        self, workspace: Workspace, description: str | None
    ) -> None:
        if workspace.profile:
            workspace.profile.description = description
            return
        if description:
            self.workspaces.add(
                WorkspaceProfile(
                    workspace_id=workspace.id,
                    description=description,
                )
            )

    def _member_subject_count(
        self, workspace_id: int, membership: Membership
    ) -> tuple[int, str]:
        if membership.role == MembershipRole.TEACHER.value:
            assignments = self.subject_memberships.list_teacher_assignments_for_membership(
                membership.id, workspace_id
            )
            return len(assignments), "assigned_subjects_count"
        if membership.role == MembershipRole.STUDENT.value:
            assignments = self.subject_memberships.list_student_assignments_for_membership(
                membership.id, workspace_id
            )
            return len(assignments), "enrolled_subjects_count"
        return 0, "assigned_subjects_count"

    def _serialize_workspace_member(
        self,
        membership: Membership,
        user,
        *,
        subject_count: int,
        subject_count_field: str,
    ) -> dict:
        payload = {
            "user_id": user.id,
            "membership_id": membership.id,
            "full_name": user.full_name,
            "email": user.email,
            "avatar_url": user.profile_image_url,
            "user_status": user.user_status,
            "workspace_role": membership.role,
            "membership_role": membership.role,
            "created_at": membership.created_at.isoformat()
            if membership.created_at
            else None,
            subject_count_field: subject_count,
        }
        return payload

    def _serialize_workspace_teacher(self, membership: Membership, user) -> dict:
        return self._serialize_workspace_member(
            membership,
            user,
            subject_count=0,
            subject_count_field="assigned_subjects_count",
        )

    def _serialize_institution_workspace_test(self, test: Test) -> dict:
        creator = test.created_by
        creator_user = creator.user if creator else None
        return {
            "test_id": test.id,
            "name": test.name,
            "slug": test.slug,
            "description": test.description,
            "subject_id": test.subject_id,
            "subject_name": test.subject.name if test.subject else None,
            "status": test.status,
            "total_score": float(test.total_score) if test.total_score is not None else None,
            "target_total_score": float(test.target_total_score)
            if test.target_total_score is not None
            else None,
            "passing_score": float(test.passing_score)
            if test.passing_score is not None
            else None,
            "availability_time_mode": test.availability_time_mode,
            "starts_at": format_local_datetime(test.starts_at),
            "duration_minutes": test.duration_minutes,
            "created_by_membership_id": test.created_by_membership_id,
            "created_by": {
                "membership_id": creator.id if creator else None,
                "user_id": creator_user.id if creator_user else None,
                "full_name": creator_user.full_name if creator_user else None,
                "email": creator_user.email if creator_user else None,
                "role": creator.role if creator else None,
            },
            "published_at": format_local_datetime(test.published_at),
            "closed_at": format_local_datetime(test.closed_at),
            "archived_at": format_local_datetime(test.archived_at),
            "created_at": format_local_datetime(test.created_at),
            "updated_at": format_local_datetime(test.updated_at),
        }

    def _serialize_workspace(
        self, workspace: Workspace, *, role: str | None, membership_id: int | None
    ) -> dict:
        return {
            "id": workspace.id,
            "name": workspace.name,
            "slug": workspace.slug,
            "kind": workspace.kind,
            "status": workspace.status,
            "join_code": workspace.join_code,
            "logo_url": workspace.logo_url,
            "membership_id": membership_id,
            "role": role,
            "is_owner": workspace.owner_membership_id == membership_id,
        }

    def _serialize_workspace_detail(self, workspace: Workspace) -> dict:
        return {
            "id": workspace.id,
            "name": workspace.name,
            "slug": workspace.slug,
            "kind": workspace.kind,
            "status": workspace.status,
            "join_code": workspace.join_code,
            "logo_url": workspace.logo_url,
            "owner_user_id": workspace.owner_user_id,
            "owner_membership_id": workspace.owner_membership_id,
            "subject_assignment_mode": workspace.subject_assignment_mode,
            "is_verified_by_superadmin": workspace.is_verified_by_superadmin,
        }

    def _resolve_member_last_activity_at(
        self, user, workspace_id: int
    ) -> datetime | None:
        attempt_activity = self.test_attempts.get_user_last_activity_in_workspace(
            user.id, workspace_id
        )
        if attempt_activity and user.last_login_at:
            return max(attempt_activity, user.last_login_at)
        return attempt_activity or user.last_login_at

    def _serialize_member_identity(
        self, user, membership: Membership, last_activity_at: datetime | None
    ) -> dict:
        payload = {
            "user_id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "last_activity_at": last_activity_at.isoformat()
            if last_activity_at
            else None,
            "status": membership.status,
        }
        if user.profile_image_url:
            payload["avatar"] = user.profile_image_url
        return payload

    def _serialize_member_subjects(
        self, membership: Membership, workspace_id: int
    ) -> list[dict]:
        if membership.role == MembershipRole.TEACHER.value:
            links = self.subject_memberships.list_teacher_assignments_for_membership(
                membership.id, workspace_id
            )
        else:
            links = self.subject_memberships.list_student_assignments_for_membership(
                membership.id, workspace_id
            )
        subjects: list[dict] = []
        for link in links:
            subject = link.subject
            if not subject:
                continue
            subjects.append(
                {
                    "subject_id": subject.id,
                    "subject_name": subject.name,
                }
            )
        return subjects

    def _fetch_tests_by_ids(self, test_ids: list[int]) -> dict[int, Test]:
        if not test_ids:
            return {}
        rows = db.session.execute(
            db.select(Test).where(Test.id.in_(test_ids))
        ).scalars().all()
        return {test.id: test for test in rows}

    def _test_availability_type(self, test: Test | None) -> str | None:
        if not test:
            return None
        return (
            test.availability_time_mode or AvailabilityTimeMode.SCHEDULED.value
        ).upper()

    def _serialize_member_upcoming_test(
        self, upcoming: dict, test: Test | None
    ) -> dict:
        mode = upcoming.get("availability_time_mode")
        starts_at = None
        if mode == AvailabilityTimeMode.FLEXIBLE.value:
            window = upcoming.get("availability_window") or {}
            starts_at = window.get("available_from")
        else:
            starts_at = upcoming.get("start_time")

        payload = {
            "test_id": upcoming["test_id"],
            "test_name": upcoming["title"],
            "subject_name": upcoming.get("subject"),
            "availability_type": mode,
            "duration_minutes": test.duration_minutes if test else None,
        }
        if starts_at:
            payload["starts_at"] = starts_at
        return payload

    def _serialize_member_completed_test(self, attempt: TestAttempt) -> dict:
        test = attempt.test
        availability_type = self._test_availability_type(test)
        test_date = None
        if attempt.submitted_at:
            test_date = ensure_local_aware(attempt.submitted_at).date().isoformat()
        elif attempt.started_at:
            test_date = ensure_local_aware(attempt.started_at).date().isoformat()

        return {
            "test_id": test.id if test else None,
            "test_name": test.name if test else None,
            "test_type": availability_type,
            "test_date": test_date,
            "test_start_time": format_local_datetime(attempt.started_at),
            "subject_name": test.subject.name if test and test.subject else None,
            "duration_minutes": test.duration_minutes if test else None,
        }

    def _serialize_recently_active_member(
        self,
        membership: Membership,
        user,
        last_activity_at: datetime | None,
    ) -> dict:
        payload = {
            "membership_id": membership.id,
            "user_id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": membership.role,
            "status": membership.status,
            "last_activity_at": last_activity_at.isoformat()
            if last_activity_at
            else None,
        }
        if user.profile_image_url:
            payload["avatar"] = user.profile_image_url
        return payload
