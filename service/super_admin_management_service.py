from utils.messages import Messages
from datetime import datetime, timezone

from flask import current_app

from models import Membership, User, Workspace
from repositories.session_repository import SessionRepository
from repositories.super_admin_management_repository import SuperAdminManagementRepository
from repositories.user_repository import UserRepository
from service.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from utils.db import db
from utils.enums import UserStatus, WorkspaceStatus
from utils.pagination import build_pagination_meta, normalize_pagination


class SuperAdminManagementService:
    def __init__(self):
        self.repo = SuperAdminManagementRepository()
        self.users = UserRepository()
        self.sessions = SessionRepository()

    def suspend_organization(
        self,
        organization_id: int,
        *,
        reason: str,
        actor_user: User,
    ) -> dict:
        workspace = self._get_organization_or_raise(organization_id)

        if workspace.status == WorkspaceStatus.SUSPENDED.value:
            raise ConflictError(Messages.ORGANIZATION_IS_ALREADY_SUSPENDED)

        reason = (reason or "").strip()
        if not reason:
            raise ValidationError(Messages.SUSPENSION_REASON_IS_REQUIRED)

        now = datetime.now(timezone.utc)
        workspace.status = WorkspaceStatus.SUSPENDED.value
        workspace.suspended_at = now
        workspace.suspension_reason = reason
        db.session.commit()

        current_app.logger.info(
            "event=organization_suspended organization_id=%s organization_type=%s actor_user_id=%s",
            workspace.id,
            workspace.kind,
            actor_user.id,
        )

        return {
            "message": Messages.ORGANIZATION_SUSPENDED_SUCCESSFULLY,
            "organization": self._serialize_organization_summary(workspace),
        }

    def restore_organization(
        self, organization_id: int, *, actor_user: User
    ) -> dict:
        workspace = self._get_organization_or_raise(organization_id)

        if workspace.status != WorkspaceStatus.SUSPENDED.value:
            raise ValidationError(Messages.ORGANIZATION_IS_NOT_SUSPENDED)

        workspace.status = WorkspaceStatus.ACTIVE.value
        workspace.suspended_at = None
        workspace.suspension_reason = None
        db.session.commit()

        current_app.logger.info(
            "event=organization_restored organization_id=%s organization_type=%s actor_user_id=%s",
            workspace.id,
            workspace.kind,
            actor_user.id,
        )

        return {
            "message": Messages.ORGANIZATION_RESTORED_SUCCESSFULLY,
            "organization": self._serialize_organization_detail(workspace),
        }

    def get_organization_details(self, organization_id: int) -> dict:
        workspace = self._get_organization_or_raise(organization_id)
        return self._serialize_organization_detail(workspace)

    def suspend_user(
        self,
        user_id: int,
        *,
        reason: str,
        actor_user: User,
    ) -> dict:
        user = self.users.get_by_id(user_id)
        if not user:
            raise NotFoundError(Messages.USER_NOT_FOUND)

        if user.id == actor_user.id:
            raise ForbiddenError(Messages.SUPER_ADMINS_CANNOT_SUSPEND_THEIR_OWN_ACCOUNT)

        if user.user_status == UserStatus.SUSPENDED.value:
            raise ConflictError(Messages.USER_IS_ALREADY_SUSPENDED)

        reason = (reason or "").strip()
        if not reason:
            raise ValidationError(Messages.SUSPENSION_REASON_IS_REQUIRED)

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
            "message": Messages.USER_SUSPENDED_SUCCESSFULLY,
            "user": self._serialize_managed_user(user, memberships),
        }

    def restore_user(self, user_id: int, *, actor_user: User) -> dict:
        user = self.users.get_by_id(user_id)
        if not user:
            raise NotFoundError(Messages.USER_NOT_FOUND)

        if user.user_status != UserStatus.SUSPENDED.value:
            raise ValidationError(Messages.USER_IS_NOT_SUSPENDED)

        user.user_status = UserStatus.ACTIVE.value
        user.suspended_at = None
        user.suspension_reason = None
        db.session.commit()

        current_app.logger.info(
            "event=user_restored user_id=%s actor_user_id=%s",
            user.id,
            actor_user.id,
        )

        memberships = self.repo.load_memberships_for_users([user.id]).get(user.id, [])
        return {
            "message": Messages.USER_RESTORED_SUCCESSFULLY,
            "user": self._serialize_managed_user(user, memberships),
        }

    def get_user_details(self, user_id: int) -> dict:
        user = self.users.get_by_id(user_id)
        if not user:
            raise NotFoundError(Messages.USER_NOT_FOUND)

        memberships = self.repo.load_memberships_for_users([user.id]).get(user.id, [])
        return self._serialize_user_detail(user, memberships)

    def list_users(
        self,
        *,
        page: int | None = None,
        per_page: int | None = None,
        role: str | None = None,
        organization_id: int | None = None,
        status: str | None = None,
        search: str | None = None,
        super_admin_only: bool = False,
    ) -> dict:
        page, per_page, offset = normalize_pagination(page, per_page)
        rows, memberships_by_user, total = self.repo.list_users_with_memberships(
            role=role,
            organization_id=organization_id,
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

    def _get_organization_or_raise(self, organization_id: int) -> Workspace:
        workspace = self.repo.get_workspace_by_id(organization_id)
        if not workspace:
            raise NotFoundError(Messages.ORGANIZATION_NOT_FOUND)
        return workspace

    def _serialize_organization_summary(self, workspace: Workspace) -> dict:
        counts = self.repo.get_institution_member_counts(workspace.id)
        tests_count = self.repo.count_institution_tests(workspace.id)
        return {
            "id": workspace.id,
            "name": workspace.name,
            "organization_type": workspace.kind,
            "status": workspace.status,
            "suspended_at": workspace.suspended_at.isoformat()
            if workspace.suspended_at
            else None,
            "suspension_reason": workspace.suspension_reason,
            "students_count": counts["students_count"],
            "teachers_count": counts["teachers_count"],
            "tests_count": int(tests_count),
        }

    def _serialize_organization_detail(self, workspace: Workspace) -> dict:
        counts = self.repo.get_institution_member_counts(workspace.id)
        owner = self.repo.get_institution_owner(workspace)
        profile = workspace.profile
        return {
            "id": workspace.id,
            "name": workspace.name,
            "slug": workspace.slug,
            "organization_type": workspace.kind,
            "status": workspace.status,
            "created_at": workspace.created_at.isoformat()
            if workspace.created_at
            else None,
            "updated_at": workspace.updated_at.isoformat()
            if workspace.updated_at
            else None,
            "suspended_at": workspace.suspended_at.isoformat()
            if workspace.suspended_at
            else None,
            "suspension_reason": workspace.suspension_reason,
            "is_verified_by_superadmin": workspace.is_verified_by_superadmin,
            "logo_url": workspace.logo_url,
            "join_code": workspace.join_code,
            "owner": {
                "user_id": owner.id,
                "name": owner.full_name,
                "email": owner.email,
            }
            if owner
            else None,
            "profile": {
                "country": profile.country if profile else None,
                "city": profile.city if profile else None,
                "website_url": profile.website_url if profile else None,
                "description": profile.description if profile else None,
            },
            "admins_count": counts["admins_count"],
            "students_count": counts["students_count"],
            "teachers_count": counts["teachers_count"],
            "active_users_count": self.repo.count_institution_active_users(
                workspace.id
            ),
            "tests_count": int(self.repo.count_institution_tests(workspace.id)),
            "attempts_count": int(
                self.repo.count_institution_attempts(workspace.id)
            ),
        }

    def _serialize_user_detail(
        self, user: User, memberships: list[Membership] | None = None
    ) -> dict:
        base = self._serialize_managed_user(user, memberships)
        last_attempt_activity = self.repo.get_user_last_attempt_activity(user.id)
        last_activity_at = last_attempt_activity or user.last_login_at
        membership_items = []
        for membership in memberships or []:
            workspace = membership.workspace
            membership_items.append(
                {
                    "membership_id": membership.id,
                    "role": membership.role,
                    "status": membership.status,
                    "joined_at": membership.joined_at.isoformat()
                    if membership.joined_at
                    else None,
                    "organization": self._serialize_organization_ref(workspace)
                    if workspace
                    else None,
                }
            )
        return {
            **base,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            "last_login_at": user.last_login_at.isoformat()
            if user.last_login_at
            else None,
            "last_activity_at": last_activity_at.isoformat()
            if last_activity_at
            else None,
            "email_verified": user.email_verified,
            "is_superadmin": user.is_superadmin,
            "memberships": membership_items,
            "created_tests_count": int(
                self.repo.count_user_created_tests(user.id)
            ),
            "completed_attempts_count": int(
                self.repo.count_user_completed_attempts(user.id)
            ),
        }

    def _serialize_organization_ref(self, workspace: Workspace) -> dict:
        return {
            "id": workspace.id,
            "name": workspace.name,
            "organization_type": workspace.kind,
            "status": workspace.status,
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

        organizations = []
        seen_workspace_ids: set[int] = set()
        for membership in memberships:
            workspace = membership.workspace
            if not workspace or workspace.id in seen_workspace_ids:
                continue
            seen_workspace_ids.add(workspace.id)
            organizations.append(self._serialize_organization_ref(workspace))

        return {
            "id": user.id,
            "name": user.full_name,
            "email": user.email,
            "status": user.user_status,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "suspended_at": user.suspended_at.isoformat() if user.suspended_at else None,
            "suspension_reason": user.suspension_reason,
            "roles": roles,
            "organizations": organizations,
        }
