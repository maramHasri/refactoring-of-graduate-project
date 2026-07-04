from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from utils.db import db
from utils.mixins import CreatedAtMixin, TimestampMixin


class StudentGroup(db.Model, TimestampMixin):
    __tablename__ = "student_groups"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    workspace_id = db.Column(
        db.Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id = db.Column(
        db.Integer,
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(String(255), nullable=False)
    description = db.Column(Text, nullable=True)
    created_by_membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    workspace = relationship("Workspace", back_populates="student_groups")
    subject = relationship("Subject", back_populates="student_groups")
    created_by = relationship(
        "Membership",
        foreign_keys=[created_by_membership_id],
    )
    members = relationship(
        "StudentGroupMember",
        back_populates="group",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    __table_args__ = (
        UniqueConstraint(
            "subject_id",
            "name",
            name="uq_student_groups_subject_name",
        ),
        Index("ix_student_groups_workspace_subject", "workspace_id", "subject_id"),
    )

    def __repr__(self):
        return f"<StudentGroup id={self.id} name={self.name} subject_id={self.subject_id}>"


class StudentGroupMember(db.Model, CreatedAtMixin):
    __tablename__ = "student_group_members"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    group_id = db.Column(
        db.Integer,
        ForeignKey("student_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_membership_id = db.Column(
        db.Integer,
        ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    group = relationship("StudentGroup", back_populates="members")
    student_membership = relationship(
        "Membership",
        foreign_keys=[student_membership_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "student_membership_id",
            name="uq_student_group_member",
        ),
        Index(
            "ix_student_group_members_group_student",
            "group_id",
            "student_membership_id",
        ),
    )

    def __repr__(self):
        return (
            f"<StudentGroupMember group_id={self.group_id} "
            f"student_membership_id={self.student_membership_id}>"
        )
