from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from utils.db import db
from utils.mixins import TimestampMixin


class TestStudentAssignment(db.Model, TimestampMixin):
    __tablename__ = "test_student_assignments"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    test_id = db.Column(
        db.Integer,
        ForeignKey("tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_by_membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    invite_status = db.Column(
        String(30),
        nullable=False,
        default="PENDING",
        server_default="PENDING",
    )
    invite_sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    invite_error = db.Column(Text, nullable=True)

    test = relationship("Test", back_populates="assigned_students")
    student_membership = relationship(
        "Membership",
        foreign_keys=[student_membership_id],
    )
    assigned_by = relationship(
        "Membership",
        foreign_keys=[assigned_by_membership_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "test_id",
            "student_membership_id",
            name="uq_test_student_assignment",
        ),
        Index(
            "ix_test_student_assignments_test_invite_status",
            "test_id",
            "invite_status",
        ),
    )

    def __repr__(self):
        return (
            f"<TestStudentAssignment test_id={self.test_id} "
            f"student_membership_id={self.student_membership_id}>"
        )
