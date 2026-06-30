from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from utils.db import db
from utils.mixins import CreatedAtMixin


class AttemptGradingAuditLog(db.Model, CreatedAtMixin):
    __tablename__ = "attempt_grading_audit_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    attempt_id = db.Column(
        db.Integer,
        ForeignKey("test_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action = db.Column(String(50), nullable=False, index=True)
    actor_membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_user_id = db.Column(
        db.Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    details = db.Column(Text, nullable=True)

    attempt = relationship("TestAttempt", back_populates="grading_audit_logs")

    __table_args__ = (
        Index("ix_attempt_grading_audit_attempt_action", "attempt_id", "action"),
    )

    def __repr__(self):
        return f"<AttemptGradingAuditLog id={self.id} action={self.action}>"
