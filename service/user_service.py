"""
User profile — self-service read/update for the authenticated user.
"""

from utils.messages import Messages
from models import User
from repositories.user_repository import UserRepository
from service.exceptions import ValidationError
from utils.db import db


class UserService:
    def __init__(self):
        self.users = UserRepository()

    def get_profile(self, user: User) -> dict:
        return self.serialize_profile(user)

    def update_profile(self, user: User, data: dict) -> User:
        if not data:
            raise ValidationError(Messages.AT_LEAST_ONE_PROFILE_FIELD_IS_REQUIRED)
        self._apply_user_profile_updates(user, data)
        db.session.commit()
        return user

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
