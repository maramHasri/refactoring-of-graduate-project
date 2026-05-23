"""
Pin the platform super-admin account (idempotent).
Credentials from .env: SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, SUPER_ADMIN_FULL_NAME
"""
from flask import current_app

from models import User
from utils.db import db
from utils.enums import UserStatus
from utils.security import hash_password


def seed_super_admin():
    email = current_app.config["SUPER_ADMIN_EMAIL"].lower().strip()
    existing = db.session.execute(
        db.select(User).where(User.email == email)
    ).scalar_one_or_none()

    if existing:
        existing.is_superadmin = True
        existing.email_verified = True
        existing.user_status = UserStatus.ACTIVE.value
        existing.full_name = current_app.config["SUPER_ADMIN_FULL_NAME"]
        if not existing.password_hash.startswith("$2"):
            existing.password_hash = hash_password(
                current_app.config["SUPER_ADMIN_PASSWORD"]
            )
        db.session.commit()
        print(f"Super admin updated: {email}")
        return existing

    user = User(
        email=email,
        password_hash=hash_password(current_app.config["SUPER_ADMIN_PASSWORD"]),
        full_name=current_app.config["SUPER_ADMIN_FULL_NAME"],
        user_status=UserStatus.ACTIVE.value,
        email_verified=True,
        is_superadmin=True,
    )
    db.session.add(user)
    db.session.commit()
    print(f"Super admin created: {email}")
    return user
