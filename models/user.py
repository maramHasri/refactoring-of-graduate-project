from sqlalchemy import Boolean, Index, String, event
from sqlalchemy.orm import relationship, validates

from utils.db import db
from utils.enums import UserStatus
from utils.mixins import TimestampMixin


class User(db.Model, TimestampMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    full_name = db.Column(String(255), nullable=False)
    email = db.Column(String(255), nullable=False, unique=True)
    password_hash = db.Column(String(255), nullable=False)
    avatar_url = db.Column(String(255), nullable=True)
    phone_number = db.Column(String(20), nullable=True)
    user_status = db.Column(
        String(30),
        nullable=False,
        default=UserStatus.PENDING_VERIFICATION.value,
        server_default=UserStatus.PENDING_VERIFICATION.value,
    )
    email_verified = db.Column(Boolean, nullable=False, default=False)
    is_superadmin = db.Column(Boolean, nullable=False, default=False)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    password_reset_codes = relationship(
        "PasswordResetCode",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    email_verification_tokens = relationship(
        "EmailVerificationToken",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    sessions = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    owned_workspaces = relationship(
        "Workspace",
        back_populates="owner",
        foreign_keys="Workspace.owner_user_id",
        lazy="dynamic",
    )
    memberships = relationship(
        "Membership",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    test_attempts = relationship(
        "TestAttempt",
        back_populates="user",
        lazy="dynamic",
    )
    owned_questions = relationship(
        "Question",
        back_populates="owner",
        lazy="dynamic",
    )
    __table_args__ = (Index("ix_users_user_status", "user_status"),)

    @validates("email")
    def _normalize_email(self, _key, value: str) -> str:
        if value is not None:
            return value.lower().strip()
        return value

    def __repr__(self):
        return f"<User id={self.id} email={self.email}>"


@event.listens_for(User, "before_insert")
@event.listens_for(User, "before_update")
def _ensure_email_lowercase(_mapper, _connection, target: User):
    if target.email:
        target.email = target.email.lower().strip()
