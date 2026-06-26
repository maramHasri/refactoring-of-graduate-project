from sqlalchemy import Float, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from utils.db import db
from utils.enums import AvailabilityTimeMode, TestAttemptStatus, TestStatus
from utils.mixins import TimestampMixin


class Test(db.Model, TimestampMixin):
    __tablename__ = "tests"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(String(255), nullable=False)
    slug = db.Column(String(255), nullable=False, unique=True)
    grading_mode = db.Column(String(50), nullable=True)
    description = db.Column(Text, nullable=True)
    subject_id = db.Column(
        db.Integer,
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    total_score = db.Column(Numeric(8, 2), nullable=True)
    passing_score = db.Column(Numeric(8, 2), nullable=True)
    auto_distribute_scores = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    scoring_config = db.Column(Text, nullable=True)
    settings_config = db.Column(Text, nullable=True)
    created_by_membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = db.Column(
        String(30),
        nullable=False,
        default=TestStatus.DRAFT.value,
        server_default=TestStatus.DRAFT.value,
    )
    availability_time_mode = db.Column(String(30), nullable=True)
    starts_at = db.Column(db.DateTime(timezone=True), nullable=True)
    duration_minutes = db.Column(Integer, nullable=True)
    entry_window_minutes = db.Column(Integer, nullable=True)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    scheduled_publish_at = db.Column(db.DateTime(timezone=True), nullable=True)
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)

    created_by = relationship(
        "Membership",
        back_populates="created_tests",
        foreign_keys=[created_by_membership_id],
    )
    attempts = relationship(
        "TestAttempt",
        back_populates="test",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    test_questions = relationship(
        "TestQuestion",
        back_populates="test",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    subject = relationship("Subject")

    __table_args__ = (
        Index("ix_tests_status", "status"),
        Index("ix_tests_availability_time_mode", "availability_time_mode"),
    )

    def __repr__(self):
        return f"<Test id={self.id} slug={self.slug}>"


class TestAttempt(db.Model):
    __tablename__ = "test_attempts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_id = db.Column(
        db.Integer,
        ForeignKey("tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = db.Column(
        String(30),
        nullable=False,
        default=TestAttemptStatus.IN_PROGRESS.value,
        server_default=TestAttemptStatus.IN_PROGRESS.value,
    )
    started_at = db.Column(db.DateTime(timezone=True), nullable=False)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_activity_at = db.Column(db.DateTime(timezone=True), nullable=True)
    submission_source = db.Column(String(30), nullable=True)
    raw_score = db.Column(Float, nullable=True)
    final_score = db.Column(Float, nullable=True)

    test = relationship("Test", back_populates="attempts")
    student_membership = relationship(
        "Membership",
        back_populates="test_attempts",
        foreign_keys=[student_membership_id],
    )
    user = relationship("User", back_populates="test_attempts")
    answers = relationship(
        "AttemptAnswer",
        back_populates="attempt",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    proctoring_session = relationship(
        "ProctoringSession",
        back_populates="test_attempt",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_test_attempts_test_student", "test_id", "student_membership_id"),
        Index("ix_test_attempts_test_status", "test_id", "status"),
        Index("ix_test_attempts_user_id", "user_id"),
    )

    def __repr__(self):
        return f"<TestAttempt id={self.id} test_id={self.test_id} status={self.status}>"
