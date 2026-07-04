"""
User profile — self-service read/update for the authenticated user.
"""
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
            raise ValidationError("At least one profile field is required")

        if "full_name" in data:
            if data["full_name"] is None:
                raise ValidationError("full_name cannot be empty")
            name = data["full_name"].strip()
            if not name:
                raise ValidationError("full_name cannot be empty")
            user.full_name = name

        if "phone_number" in data:
            user.phone_number = (data.get("phone_number") or "").strip() or None

        if "avatar_url" in data:
            user.profile_image_url = (data.get("avatar_url") or "").strip() or None

        db.session.commit()
        return user

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
