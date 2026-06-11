from sqlalchemy import Boolean, ForeignKey, Index, String, Text, event  # noqa: F401 Index unused but kept
from sqlalchemy.orm import relationship, validates

from utils.db import db
from utils.mixins import CreatedAtMixin


class PasswordResetCode(db.Model):
    __tablename__ = "password_reset_codes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reset_code_hash = db.Column(String(255), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    is_used = db.Column(Boolean, nullable=False, default=False)

    user = relationship("User", back_populates="password_reset_codes")

    __table_args__ = (
        Index("ix_password_reset_codes_user_id_is_used", "user_id", "is_used"),
    )

    def __repr__(self):
        return f"<PasswordResetCode id={self.id} user_id={self.user_id}>"


class EmailOtp(db.Model, CreatedAtMixin):
    """Hashed one-time codes for email verification (never store plain OTP)."""

    __tablename__ = "email_otps"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(String(255), nullable=False, index=True)
    user_id = db.Column(
        db.Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    otp_hash = db.Column(String(255), nullable=False)
    purpose = db.Column(String(30), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    is_used = db.Column(Boolean, nullable=False, default=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    verify_attempts = db.Column(db.Integer, nullable=False, default=0)

    user = relationship("User", back_populates="email_otps")

    __table_args__ = (
        Index("ix_email_otps_email_is_used", "email", "is_used"),
    )

    @validates("email")
    def _normalize_email(self, _key, value: str) -> str:
        if value is not None:
            return value.lower().strip()
        return value

    def __repr__(self):
        return f"<EmailOtp id={self.id} email={self.email} purpose={self.purpose}>"


@event.listens_for(EmailOtp, "before_insert")
@event.listens_for(EmailOtp, "before_update")
def _ensure_otp_email_lowercase(_mapper, _connection, target: EmailOtp):
    if target.email:
        target.email = target.email.lower().strip()


class RegistrationIntent(db.Model, CreatedAtMixin):
    """
    Owner registration payload.
    SOLO: consumed on OTP verify (workspace created immediately).
    INSTITUTION: linked to user on OTP verify; workspace created on super admin approve.
    """

    __tablename__ = "registration_intents"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(String(255), nullable=False)
    full_name = db.Column(String(255), nullable=False)
    phone_number = db.Column(String(20), nullable=True)
    workspace_name = db.Column(String(255), nullable=False)
    slug = db.Column(String(255), nullable=False)
    workspace_kind = db.Column(String(50), nullable=False)
    country = db.Column(String(120), nullable=True)
    city = db.Column(String(120), nullable=True)
    website_url = db.Column(String(255), nullable=True)
    description = db.Column(Text, nullable=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    consumed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    user_id = db.Column(
        db.Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    approval_status = db.Column(String(30), nullable=True)
    rejection_reason = db.Column(Text, nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="institution_registration")

    @validates("email")
    def _normalize_intent_email(self, _key, value: str) -> str:
        if value is not None:
            return value.lower().strip()
        return value

    def __repr__(self):
        return f"<RegistrationIntent id={self.id} email={self.email}>"


@event.listens_for(RegistrationIntent, "before_insert")
@event.listens_for(RegistrationIntent, "before_update")
def _ensure_intent_email_lowercase(_mapper, _connection, target: RegistrationIntent):
    if target.email:
        target.email = target.email.lower().strip()


class UserSession(db.Model, CreatedAtMixin):
    __tablename__ = "user_sessions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    access_token_id = db.Column(String(255), nullable=False, unique=True)
    ip_address = db.Column(String(45), nullable=True)
    user_agent = db.Column(Text, nullable=True)
    is_active = db.Column(Boolean, nullable=False, default=True)
    last_used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index("ix_user_sessions_user_id_is_active", "user_id", "is_active"),
    )

    def __repr__(self):
        return f"<UserSession id={self.id} user_id={self.user_id}>"
