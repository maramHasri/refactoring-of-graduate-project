"""Persisted academic-integrity reports created on PROCTORING_AUTO termination.

Independent from Support ``Report`` tickets (``models/report.py``).
"""

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from utils.db import db
from utils.enums import ProctoringIntegrityReportStatus
from utils.mixins import TimestampMixin


class ProctoringIntegrityReport(db.Model, TimestampMixin):
    __tablename__ = "proctoring_integrity_reports"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    attempt_id = db.Column(
        db.Integer,
        ForeignKey("test_attempts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    test_id = db.Column(
        db.Integer,
        ForeignKey("tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id = db.Column(
        db.Integer,
        ForeignKey("subjects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workspace_id = db.Column(
        db.Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    teacher_membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    student_membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
    )
    proctoring_session_id = db.Column(
        db.Integer,
        ForeignKey("proctoring_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Identity snapshot (immutable after create)
    student_name = db.Column(String(255), nullable=False)
    teacher_name = db.Column(String(255), nullable=True)
    subject_name = db.Column(String(255), nullable=True)
    test_name = db.Column(String(255), nullable=False)
    workspace_name = db.Column(String(255), nullable=False)

    # Integrity snapshot
    risk_percentage = db.Column(Float, nullable=False, default=0.0)
    effective_violation_score = db.Column(Integer, nullable=False, default=0)
    violations_count = db.Column(Integer, nullable=False, default=0)
    high_severity_count = db.Column(Integer, nullable=False, default=0)
    medium_severity_count = db.Column(Integer, nullable=False, default=0)
    low_severity_count = db.Column(Integer, nullable=False, default=0)

    # Attempt snapshot
    final_score = db.Column(Float, nullable=True)
    raw_score = db.Column(Float, nullable=True)
    maximum_score = db.Column(Float, nullable=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    terminated_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Termination / recommendation snapshot
    submission_source = db.Column(String(30), nullable=False)
    termination_reason = db.Column(String(80), nullable=True)
    recommendation = db.Column(String(40), nullable=False)
    recommendation_reason = db.Column(Text, nullable=True)

    # Review workflow
    status = db.Column(
        String(30),
        nullable=False,
        default=ProctoringIntegrityReportStatus.PENDING.value,
        server_default=ProctoringIntegrityReportStatus.PENDING.value,
        index=True,
    )
    reviewed_by_membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    review_note = db.Column(Text, nullable=True)

    attempt = relationship("TestAttempt")
    test = relationship("Test")
    subject = relationship("Subject")
    workspace = relationship("Workspace")
    teacher_membership = relationship(
        "Membership", foreign_keys=[teacher_membership_id]
    )
    student_membership = relationship(
        "Membership", foreign_keys=[student_membership_id]
    )
    reviewed_by = relationship(
        "Membership", foreign_keys=[reviewed_by_membership_id]
    )
    proctoring_session = relationship("ProctoringSession")

    __table_args__ = (
        UniqueConstraint("attempt_id", name="uq_proctoring_integrity_reports_attempt"),
        Index(
            "ix_pir_workspace_status_created",
            "workspace_id",
            "status",
            "created_at",
        ),
        Index("ix_pir_workspace_test", "workspace_id", "test_id"),
        Index("ix_pir_workspace_subject", "workspace_id", "subject_id"),
    )

    def __repr__(self):
        return (
            f"<ProctoringIntegrityReport id={self.id} attempt_id={self.attempt_id} "
            f"status={self.status}>"
        )
