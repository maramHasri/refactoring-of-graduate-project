"""
Proctoring domain — sessions, events, violations, evidence, audit logs.
"""
from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from utils.db import db
from utils.enums import (
    ProctoringSessionStatus,
    ProctoringViolationStatus,
    ViolationSeverity,
)
from utils.mixins import TimestampMixin, CreatedAtMixin


class ProctoringSession(db.Model, TimestampMixin):
    __tablename__ = "proctoring_sessions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    test_attempt_id = db.Column(
        db.Integer,
        ForeignKey("test_attempts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    workspace_id = db.Column(
        db.Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = db.Column(
        String(30),
        nullable=False,
        default=ProctoringSessionStatus.ACTIVE.value,
        server_default=ProctoringSessionStatus.ACTIVE.value,
    )
    started_at = db.Column(db.DateTime(timezone=True), nullable=False)
    ended_at = db.Column(db.DateTime(timezone=True), nullable=True)
    violation_score = db.Column(Integer, nullable=False, default=0, server_default="0")
    tab_switch_count = db.Column(Integer, nullable=False, default=0, server_default="0")
    settings_snapshot = db.Column(JSONB, nullable=True)
    device_metadata = db.Column(JSONB, nullable=True)
    browser_metadata = db.Column(JSONB, nullable=True)

    test_attempt = relationship("TestAttempt", back_populates="proctoring_session")
    events = relationship(
        "ProctoringEvent",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    violations = relationship(
        "ProctoringViolation",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    audit_logs = relationship(
        "ProctoringAuditLog",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    __table_args__ = (
        Index("ix_proctoring_sessions_workspace_status", "workspace_id", "status"),
    )

    def __repr__(self):
        return f"<ProctoringSession id={self.id} attempt_id={self.test_attempt_id}>"


class ProctoringEvent(db.Model, CreatedAtMixin):
    """Low-level proctoring event log (WebSocket or REST ingestion)."""

    __tablename__ = "proctoring_events"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(
        db.Integer,
        ForeignKey("proctoring_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = db.Column(String(50), nullable=False, index=True)
    payload = db.Column(JSONB, nullable=True)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False)
    source = db.Column(String(20), nullable=False, default="REST", server_default="REST")

    session = relationship("ProctoringSession", back_populates="events")

    __table_args__ = (
        Index("ix_proctoring_events_session_occurred", "session_id", "occurred_at"),
    )

    def __repr__(self):
        return f"<ProctoringEvent id={self.id} type={self.event_type}>"


class ProctoringViolation(db.Model, TimestampMixin):
    __tablename__ = "proctoring_violations"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(
        db.Integer,
        ForeignKey("proctoring_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    violation_type = db.Column(String(50), nullable=False)
    severity = db.Column(String(20), nullable=False)
    score_contribution = db.Column(Integer, nullable=False, default=0)
    description = db.Column(Text, nullable=True)
    status = db.Column(
        String(30),
        nullable=False,
        default=ProctoringViolationStatus.OPEN.value,
        server_default=ProctoringViolationStatus.OPEN.value,
    )
    reviewed_by_membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    review_notes = db.Column(Text, nullable=True)

    session = relationship("ProctoringSession", back_populates="violations")
    evidence_package = relationship(
        "ProctoringEvidencePackage",
        back_populates="violation",
        uselist=False,
        cascade="all, delete-orphan",
    )
    reviewed_by = relationship("Membership", foreign_keys=[reviewed_by_membership_id])

    __table_args__ = (
        Index("ix_proctoring_violations_session_severity", "session_id", "severity"),
    )

    def __repr__(self):
        return f"<ProctoringViolation id={self.id} type={self.violation_type}>"


class ProctoringEvidencePackage(db.Model, CreatedAtMixin):
    __tablename__ = "proctoring_evidence_packages"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    violation_id = db.Column(
        db.Integer,
        ForeignKey("proctoring_violations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    timeline_before = db.Column(JSONB, nullable=True)
    timeline_after = db.Column(JSONB, nullable=True)
    screenshots = db.Column(JSONB, nullable=True)
    video_clip_ref = db.Column(String(512), nullable=True)
    device_metadata = db.Column(JSONB, nullable=True)
    browser_metadata = db.Column(JSONB, nullable=True)
    network_metadata = db.Column(JSONB, nullable=True)
    event_logs = db.Column(JSONB, nullable=True)

    violation = relationship("ProctoringViolation", back_populates="evidence_package")

    def __repr__(self):
        return f"<ProctoringEvidencePackage id={self.id} violation_id={self.violation_id}>"


class ProctoringAuditLog(db.Model, CreatedAtMixin):
    __tablename__ = "proctoring_audit_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(
        db.Integer,
        ForeignKey("proctoring_sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    violation_id = db.Column(
        db.Integer,
        ForeignKey("proctoring_violations.id", ondelete="SET NULL"),
        nullable=True,
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
    details = db.Column(JSONB, nullable=True)

    session = relationship("ProctoringSession", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_proctoring_audit_logs_session_action", "session_id", "action"),
    )

    def __repr__(self):
        return f"<ProctoringAuditLog id={self.id} action={self.action}>"
