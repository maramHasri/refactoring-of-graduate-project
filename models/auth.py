from sqlalchemy import Boolean, ForeignKey, Index, String, Text, event
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


class EmailVerificationToken(db.Model, CreatedAtMixin):
    __tablename__ = "email_verification_tokens"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = db.Column(String(255), nullable=False)
    email = db.Column(String(255), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    is_used = db.Column(Boolean, nullable=False, default=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="email_verification_tokens")

    __table_args__ = (
        Index(
            "ix_email_verification_tokens_user_id_is_used",
            "user_id",
            "is_used",
        ),
        Index("ix_email_verification_tokens_token_hash", "token_hash"),
    )

    @validates("email")
    def _normalize_email(self, _key, value: str) -> str:
        if value is not None:
            return value.lower().strip()
        return value

    def __repr__(self):
        return f"<EmailVerificationToken id={self.id} user_id={self.user_id}>"


@event.listens_for(EmailVerificationToken, "before_insert")
@event.listens_for(EmailVerificationToken, "before_update")
def _ensure_verification_email_lowercase(_mapper, _connection, target: EmailVerificationToken):
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
