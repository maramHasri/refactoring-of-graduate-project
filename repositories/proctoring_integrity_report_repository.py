"""Repository for persisted ProctoringIntegrityReport rows."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select

from models import ProctoringIntegrityReport
from repositories.base_repository import BaseRepository
from utils.db import db


class ProctoringIntegrityReportRepository(BaseRepository):
    def get_by_id(self, report_id: int) -> ProctoringIntegrityReport | None:
        return db.session.get(ProctoringIntegrityReport, report_id)

    def count_grouped_by_status(self) -> dict[str, int]:
        """SQL aggregation of integrity report counts by status (platform-wide)."""
        rows = db.session.execute(
            select(
                ProctoringIntegrityReport.status,
                func.count(ProctoringIntegrityReport.id),
            ).group_by(ProctoringIntegrityReport.status)
        ).all()
        return {str(status): int(count or 0) for status, count in rows}

    def get_by_attempt_id(self, attempt_id: int) -> ProctoringIntegrityReport | None:
        return db.session.execute(
            select(ProctoringIntegrityReport).where(
                ProctoringIntegrityReport.attempt_id == attempt_id
            )
        ).scalar_one_or_none()

    def list_for_viewer(
        self,
        *,
        workspace_id: int,
        viewer_is_owner: bool,
        viewer_membership_id: int,
        status: str | None = None,
        test_id: int | None = None,
        subject_id: int | None = None,
        student_membership_id: int | None = None,
        search: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ProctoringIntegrityReport], int]:
        filters = [ProctoringIntegrityReport.workspace_id == workspace_id]
        if not viewer_is_owner:
            filters.append(
                ProctoringIntegrityReport.teacher_membership_id == viewer_membership_id
            )
        if status:
            filters.append(ProctoringIntegrityReport.status == status)
        if test_id is not None:
            filters.append(ProctoringIntegrityReport.test_id == test_id)
        if subject_id is not None:
            filters.append(ProctoringIntegrityReport.subject_id == subject_id)
        if student_membership_id is not None:
            filters.append(
                ProctoringIntegrityReport.student_membership_id == student_membership_id
            )
        if date_from is not None:
            filters.append(ProctoringIntegrityReport.created_at >= date_from)
        if date_to is not None:
            filters.append(ProctoringIntegrityReport.created_at <= date_to)
        if search:
            term = f"%{search.strip()}%"
            filters.append(
                or_(
                    ProctoringIntegrityReport.student_name.ilike(term),
                    ProctoringIntegrityReport.test_name.ilike(term),
                    ProctoringIntegrityReport.subject_name.ilike(term),
                    ProctoringIntegrityReport.teacher_name.ilike(term),
                )
            )

        total = (
            db.session.execute(
                select(func.count())
                .select_from(ProctoringIntegrityReport)
                .where(*filters)
            ).scalar_one()
            or 0
        )
        rows = list(
            db.session.execute(
                select(ProctoringIntegrityReport)
                .where(*filters)
                .order_by(
                    ProctoringIntegrityReport.created_at.desc(),
                    ProctoringIntegrityReport.id.desc(),
                )
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return rows, int(total)
