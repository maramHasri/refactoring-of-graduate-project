"""
Subjects and subject_memberships (pivot).

subject_memberships links memberships ↔ subjects with subject_role (TEACHER | STUDENT).
Workspace role (ADMIN/TEACHER/STUDENT) is separate from subject_role.
"""
from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from utils.db import db
from utils.enums import SubjectMembershipStatus, SubjectRole
from utils.mixins import TimestampMixin, utcnow


class Subject(db.Model, TimestampMixin):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(String(255), nullable=False)
    workspace_id = db.Column(
        db.Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code = db.Column(String(50), nullable=True)
    description = db.Column(Text, nullable=True)
    created_by_membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_archived = db.Column(Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    workspace = relationship("Workspace", back_populates="subjects")
    created_by = relationship(
        "Membership",
        back_populates="created_subjects",
        foreign_keys=[created_by_membership_id],
    )
    subject_memberships = relationship(
        "SubjectMembership",
        back_populates="subject",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    topics = relationship(
        "Topic",
        back_populates="subject",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    question_banks = relationship(
        "QuestionBank",
        back_populates="subject",
        lazy="dynamic",
    )

    __table_args__ = (
        Index("ix_subjects_workspace_name", "workspace_id", "name"),
        Index("ix_subjects_workspace_code", "workspace_id", "code"),
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def __repr__(self):
        return f"<Subject id={self.id} name={self.name}>"


class SubjectMembership(db.Model):
    """
    Pivot: subject_memberships — who teaches or studies each subject.
    subject_role is TEACHER or STUDENT (not the workspace membership role).
    """

    __tablename__ = "subject_memberships"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subject_id = db.Column(
        db.Integer,
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_role = db.Column(String(30), nullable=False)
    assigned_by_membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = db.Column(
        String(30),
        nullable=False,
        default=SubjectMembershipStatus.ACTIVE.value,
        server_default=SubjectMembershipStatus.ACTIVE.value,
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    membership = relationship(
        "Membership",
        back_populates="subject_memberships",
        foreign_keys=[membership_id],
    )
    subject = relationship("Subject", back_populates="subject_memberships")
    assigned_by = relationship(
        "Membership",
        foreign_keys=[assigned_by_membership_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "membership_id",
            "subject_id",
            name="unique_membership_subject",
        ),
        Index("ix_subject_memberships_subject_role", "subject_id", "subject_role"),
    )

    def __repr__(self):
        return (
            f"<SubjectMembership subject_id={self.subject_id} "
            f"membership_id={self.membership_id} role={self.subject_role}>"
        )


# Backward-compatible alias used in older imports
MembershipSubject = SubjectMembership
