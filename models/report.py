from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import relationship

from utils.db import db
from utils.enums import ReportCategory, ReportStatus
from utils.mixins import TimestampMixin


class Report(db.Model, TimestampMixin):
    """User-submitted support report for platform administrators."""

    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_by_user_id = db.Column(
        db.Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = db.Column(
        db.Integer,
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title = db.Column(String(255), nullable=False)
    description = db.Column(Text, nullable=False)
    category = db.Column(
        String(30),
        nullable=False,
        default=ReportCategory.OTHER.value,
        server_default=ReportCategory.OTHER.value,
    )
    status = db.Column(
        String(30),
        nullable=False,
        default=ReportStatus.UNREAD.value,
        server_default=ReportStatus.UNREAD.value,
        index=True,
    )

    created_by = relationship("User", back_populates="reports")
    workspace = relationship("Workspace", back_populates="reports")

    __table_args__ = (
        Index("ix_reports_status_category", "status", "category"),
        Index("ix_reports_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<Report id={self.id} status={self.status}>"
