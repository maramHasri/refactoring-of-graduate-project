from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from utils.db import db
from utils.mixins import CreatedAtMixin, utcnow


class Subject(db.Model, CreatedAtMixin):
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

    workspace = relationship("Workspace", back_populates="subjects")
    created_by = relationship(
        "Membership",
        back_populates="created_subjects",
        foreign_keys=[created_by_membership_id],
    )
    membership_links = relationship(
        "MembershipSubject",
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

    __table_args__ = (
        Index("ix_subjects_workspace_name", "workspace_id", "name"),
        Index("ix_subjects_workspace_code", "workspace_id", "code"),
    )

    def __repr__(self):
        return f"<Subject id={self.id} name={self.name}>"


class MembershipSubject(db.Model):
    """Links memberships to subjects (table: memberships_subjects)."""

    __tablename__ = "memberships_subjects"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id = db.Column(
        db.Integer,
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    membership = relationship("Membership", back_populates="subject_links")
    subject = relationship("Subject", back_populates="membership_links")

    __table_args__ = (
        UniqueConstraint(
            "membership_id",
            "subject_id",
            name="unique_membership_subject",
        ),
    )

    def __repr__(self):
        return f"<MembershipSubject membership_id={self.membership_id} subject_id={self.subject_id}>"
