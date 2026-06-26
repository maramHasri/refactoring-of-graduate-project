from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import relationship

from utils.db import db
from utils.mixins import TimestampMixin


class Topic(db.Model, TimestampMixin):
    __tablename__ = "topics"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(String(255), nullable=False)
    description = db.Column(Text, nullable=True)
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

    workspace = relationship("Workspace", back_populates="topics")
    subject = relationship("Subject", back_populates="topics")
    questions = relationship(
        "Question",
        back_populates="topic",
        lazy="dynamic",
    )

    __table_args__ = (
        Index("ix_topics_workspace_subject", "workspace_id", "subject_id"),
        Index("ix_topics_subject_name", "subject_id", "name"),
    )

    def __repr__(self):
        return f"<Topic id={self.id} name={self.name}>"
