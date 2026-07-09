from datetime import datetime, timezone

from flask import current_app

from models import Membership, User, Workspace
from repositories.session_repository import SessionRepository
from repositories.super_admin_management_repository import SuperAdminManagementRepository
from repositories.user_repository import UserRepository
from service.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from utils.db import db
from utils.enums import UserStatus, WorkspaceKind, WorkspaceStatus
from utils.pagination import build_pagination_meta, normalize_pagination


class SuperAdminManagementService:
    def __init__(self):
        self.repo = SuperAdminManagementRepository()
        self.users = UserRepository()
        self.sessions = SessionRepository()

    def suspend_institution(
        self,
        institution_id: int,
        *,
        reason: str,
        actor_user: User,
    ) -> dict:
        workspace = self.repo.get_workspace_by_id(institution_id)
        if not workspace:
            raise NotFoundError("Institution not found")

        if workspace.kind != WorkspaceKind.INSTITUTION.value:
            raise ValidationError(
                "Only institution workspaces can be suspended. "
                f"Workspace id={institution_id} has kind '{workspace.kind}'."
            )

        if workspace.status == WorkspaceStatus.SUSPENDED.value:
            raise ConflictError("Institution is already suspended")

        reason = (reason or "").strip()
        if not reason:
            raise ValidationError("Suspension reason is required")

        now = datetime.now(timezone.utc)
        workspace.status = WorkspaceStatus.SUSPENDED.value
        workspace.suspended_at = now
        workspace.suspension_reason = reason
        db.session.commit()

        current_app.logger.info(
            "event=institution_suspended institution_id=%s actor_user_id=%s",
            workspace.id,
            actor_user.id,
        )

        return {
            "message": "Institution suspended successfully",
            "institution": self._serialize_institution(workspace),
        }

    def suspend_user(
        self,
        user_id: int,
        *,
        reason: str,
        actor_user: User,
    ) -> dict:
        user = self.users.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        if user.id == actor_user.id:
            raise ForbiddenError("Super admins cannot suspend their own account")

        if user.user_status == UserStatus.SUSPENDED.value:
            raise ConflictError("User is already suspended")

        reason = (reason or "").strip()
        if not reason:
            raise ValidationError("Suspension reason is required")

        now = datetime.now(timezone.utc)
        user.user_status = UserStatus.SUSPENDED.value
        user.suspended_at = now
        user.suspension_reason = reason
        self.sessions.deactivate_all_for_user(user.id)
        db.session.commit()

        current_app.logger.info(
            "event=user_suspended user_id=%s actor_user_id=%s",
            user.id,
            actor_user.id,
        )

        user = self.repo.get_user_with_memberships(user.id)
        memberships = self.repo.load_memberships_for_users([user.id]).get(user.id, [])
        return {
            "message": "User suspended successfully",
            "user": self._serialize_managed_user(user, memberships),
        }

    def list_users(
        self,
        *,
        page: int | None = None,
        per_page: int | None = None,
        role: str | None = None,
        institution_id: int | None = None,
        status: str | None = None,
        search: str | None = None,
        super_admin_only: bool = False,
    ) -> dict:
        page, per_page, offset = normalize_pagination(page, per_page)
        rows, memberships_by_user, total = self.repo.list_users_with_memberships(
            role=role,
            institution_id=institution_id,
            status=status,
            search=search,
            super_admin_only=super_admin_only,
            offset=offset,
            limit=per_page,
        )
        data = [
            self._serialize_managed_user(
                user, memberships_by_user.get(user.id, [])
            )
            for user in rows
        ]
        return {
            "data": data,
            **build_pagination_meta(total=total, page=page, per_page=per_page),
        }

    def _serialize_institution(self, workspace: Workspace) -> dict:
        counts = self.repo.get_institution_member_counts(workspace.id)
        tests_count = self.repo.count_institution_tests(workspace.id)
        return {
            "id": workspace.id,
            "name": workspace.name,
            "kind": workspace.kind,
            "status": workspace.status,
            "suspended_at": workspace.suspended_at.isoformat()
            if workspace.suspended_at
            else None,
            "suspension_reason": workspace.suspension_reason,
            "students_count": counts["students_count"],
            "teachers_count": counts["teachers_count"],
            "tests_count": int(tests_count),
        }

    def _serialize_managed_user(
        self, user: User, memberships: list[Membership] | None = None
    ) -> dict:
        memberships = memberships if memberships is not None else []
        roles = sorted(
            {
                membership.role
                for membership in memberships
                if membership.status == "ACTIVE"
            }
        )
        if user.is_superadmin:
            roles.append("SUPER_ADMIN")

        institutions = []
        seen_workspace_ids: set[int] = set()
        for membership in memberships:
            if membership.status != "ACTIVE":
                continue
            workspace = membership.workspace
            if not workspace or workspace.id in seen_workspace_ids:
                continue
            seen_workspace_ids.add(workspace.id)
            institutions.append(
                {
                    "id": workspace.id,
                    "name": workspace.name,
                    "kind": workspace.kind,
                }
            )

        return {
            "id": user.id,
            "name": user.full_name,
            "email": user.email,
            "status": user.user_status,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "suspended_at": user.suspended_at.isoformat() if user.suspended_at else None,
            "suspension_reason": user.suspension_reason,
            "roles": roles,
            "institutions": institutions,
        }
