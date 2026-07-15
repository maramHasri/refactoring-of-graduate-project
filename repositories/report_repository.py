from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from models import Membership, Report
from repositories.base_repository import BaseRepository
from utils.db import db


class ReportRepository(BaseRepository):
    def get_by_id(self, report_id: int) -> Report | None:
        return db.session.get(Report, report_id)

    def get_with_relations(self, report_id: int) -> Report | None:
        return db.session.execute(
            select(Report)
            .options(
                joinedload(Report.created_by),
                joinedload(Report.workspace),
            )
            .where(Report.id == report_id)
        ).scalar_one_or_none()

    def list_for_user(self, user_id: int) -> list[Report]:
        return list(
            db.session.execute(
                select(Report)
                .where(Report.created_by_user_id == user_id)
                .order_by(Report.created_at.desc(), Report.id.desc())
            )
            .scalars()
            .all()
        )

    def list_for_super_admin(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Report], int]:
        filters = []
        if status:
            filters.append(Report.status == status)
        if category:
            filters.append(Report.category == category)

        total = (
            db.session.execute(
                select(func.count()).select_from(Report).where(*filters)
            ).scalar_one()
            or 0
        )
        rows = list(
            db.session.execute(
                select(Report)
                .options(
                    joinedload(Report.created_by),
                    joinedload(Report.workspace),
                )
                .where(*filters)
                .order_by(Report.created_at.desc(), Report.id.desc())
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return rows, int(total)

    def get_reporter_membership(self, report: Report) -> Membership | None:
        if not report.workspace_id:
            return None
        return db.session.execute(
            select(Membership).where(
                Membership.user_id == report.created_by_user_id,
                Membership.workspace_id == report.workspace_id,
            )
        ).scalar_one_or_none()

    def get_active_membership_for_user_workspace(
        self, user_id: int, workspace_id: int
    ) -> Membership | None:
        return db.session.execute(
            select(Membership).where(
                Membership.user_id == user_id,
                Membership.workspace_id == workspace_id,
                Membership.status == "ACTIVE",
            )
        ).scalar_one_or_none()
