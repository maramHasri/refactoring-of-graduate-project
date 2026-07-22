"""
User profile — self-service read/update for the authenticated user.
"""

from flask import current_app

from models import Membership, User
from repositories.session_repository import SessionRepository
from repositories.user_repository import UserRepository
from repositories.workspace_repository import MembershipRepository
from service.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from utils.app_timezone import local_timezone_now
from utils.db import db
from utils.messages import Messages


class UserService:
    def __init__(self):
        self.users = UserRepository()
        self.memberships = MembershipRepository()
        self.sessions = SessionRepository()

    def get_profile(self, user: User) -> dict:
        return self.serialize_profile(user)

    def update_profile(self, user: User, data: dict) -> User:
        if not data:
            raise ValidationError(Messages.AT_LEAST_ONE_PROFILE_FIELD_IS_REQUIRED)
        self._apply_user_profile_updates(user, data)
        db.session.commit()
        return user

    def soft_delete_own_account(self, user: User) -> dict:
        """
        Soft-delete the authenticated user's account.

        Sets deleted_at only — does not remove related data (tests, attempts,
        results, memberships, topics, audit/proctoring). Sessions are revoked.
        Distinct from SUSPENDED / DISABLED.
        """
        if user.deleted_at is not None:
            raise ConflictError(Messages.ACCOUNT_ALREADY_DELETED)

        now = local_timezone_now()
        user.deleted_at = now
        self.sessions.deactivate_all_for_user(user.id)
        db.session.commit()

        current_app.logger.info(
            "event=user_account_deleted actor_user_id=%s target_user_id=%s deleted_at=%s",
            user.id,
            user.id,
            now.isoformat(),
        )

        return {
            "message": Messages.ACCOUNT_DELETED_SUCCESSFULLY,
            "deleted_at": now.isoformat(),
        }

    def list_memberships(self, user_id: int, *, actor: User) -> dict:
        """Return every workspace membership for a user the actor may view."""
        user = self.users.get_by_id(user_id)
        if not user:
            raise NotFoundError(Messages.USER_NOT_FOUND)

        if actor.id != user.id and not actor.is_superadmin:
            raise ForbiddenError(
                Messages.INSUFFICIENT_PERMISSIONS_TO_VIEW_THIS_USERS_MEMBERSHIPS
            )

        rows = self.memberships.list_for_user(user.id)
        return {
            "user_id": user.id,
            "memberships": [self._serialize_membership(m) for m in rows],
        }

    def _apply_user_profile_updates(self, user: User, data: dict) -> None:
        if "full_name" in data:
            if data["full_name"] is None:
                raise ValidationError(Messages.FULL_NAME_CANNOT_BE_EMPTY)
            name = data["full_name"].strip()
            if not name:
                raise ValidationError(Messages.FULL_NAME_CANNOT_BE_EMPTY)
            user.full_name = name

        if "phone_number" in data:
            user.phone_number = (data.get("phone_number") or "").strip() or None

        avatar_value = None
        if "avatar_url" in data:
            avatar_value = data.get("avatar_url")
        elif "profile_image_url" in data:
            avatar_value = data.get("profile_image_url")
        if avatar_value is not None or "avatar_url" in data or "profile_image_url" in data:
            user.profile_image_url = (avatar_value or "").strip() or None

    def serialize_profile(self, user: User) -> dict:
        return {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "phone_number": user.phone_number,
            "avatar_url": user.profile_image_url,
            "email_verified": user.email_verified,
            "last_login_at": user.last_login_at.isoformat()
            if user.last_login_at
            else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }

    def _serialize_membership(self, membership: Membership) -> dict:
        workspace = membership.workspace
        is_owner = bool(
            workspace and workspace.owner_membership_id == membership.id
        )
        return {
            "membership_id": membership.id,
            "workspace": {
                "id": workspace.id,
                "name": workspace.name,
                "kind": workspace.kind,
            }
            if workspace
            else None,
            "role": membership.role,
            "is_owner": is_owner,
            "subject_role": None,
            "status": membership.status,
            "joined_at": membership.joined_at.isoformat()
            if membership.joined_at
            else None,
            "created_at": membership.created_at.isoformat()
            if membership.created_at
            else None,
        }
