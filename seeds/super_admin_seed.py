from flask import current_app

from models import User
from repositories.user_repository import UserRepository
from utils.db import db
from utils.enums import UserStatus
from utils.security import hash_password


def seed_super_admin() -> None:
    email = current_app.config.get("SUPER_ADMIN_EMAIL", "superadmin@eduforms.local").lower()
    password = current_app.config.get("SUPER_ADMIN_PASSWORD", "SuperAdmin@123")
    full_name = current_app.config.get("SUPER_ADMIN_FULL_NAME", "Platform Super Admin")

    repo = UserRepository()
    existing = repo.find_superadmin_by_email(email) or repo.find_by_email(email)
    if existing:
        existing.is_superadmin = True
        existing.email_verified = True
        existing.user_status = UserStatus.ACTIVE.value
        if password:
            existing.password_hash = hash_password(password)
        db.session.commit()
        return

    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        user_status=UserStatus.ACTIVE.value,
        email_verified=True,
        is_superadmin=True,
    )
    repo.add(user)
    db.session.commit()
