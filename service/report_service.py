from models import Report, User
from repositories.report_repository import ReportRepository
from service.exceptions import ForbiddenError, NotFoundError
from utils.db import db
from utils.enums import ReportStatus, UserStatus
from utils.messages import Messages
from utils.pagination import build_pagination_meta, normalize_pagination


class ReportService:
    def __init__(self):
        self.reports = ReportRepository()

    def create_report(
        self,
        *,
        actor_user: User,
        title: str,
        description: str,
        category: str,
        workspace_id: int | None = None,
    ) -> dict:
        if actor_user.user_status != UserStatus.ACTIVE.value:
            raise ForbiddenError(Messages.USER_ACCOUNT_IS_NOT_ACTIVE)

        resolved_workspace_id = self._resolve_workspace_context(
            actor_user, workspace_id
        )
        report = Report(
            created_by_user_id=actor_user.id,
            workspace_id=resolved_workspace_id,
            title=title.strip(),
            description=description.strip(),
            category=category,
            status=ReportStatus.UNREAD.value,
        )
        self.reports.add(report)
        db.session.commit()
        return {
            "message": Messages.REPORT_CREATED_SUCCESSFULLY,
            "report_id": report.id,
        }

    def list_my_reports(self, *, actor_user: User) -> dict:
        reports = self.reports.list_for_user(actor_user.id)
        return {
            "reports": [self._serialize_user_report_summary(report) for report in reports]
        }

    def get_my_report(self, *, actor_user: User, report_id: int) -> dict:
        report = self.reports.get_by_id(report_id)
        if not report:
            raise NotFoundError(Messages.REPORT_NOT_FOUND)
        if report.created_by_user_id != actor_user.id:
            raise ForbiddenError(Messages.REPORT_DOES_NOT_BELONG_TO_USER)
        return self._serialize_user_report_detail(report)

    def list_reports_for_super_admin(
        self,
        *,
        page: int | None = None,
        per_page: int | None = None,
        status: str | None = None,
        category: str | None = None,
    ) -> dict:
        page, per_page, offset = normalize_pagination(page, per_page)
        rows, total = self.reports.list_for_super_admin(
            status=status,
            category=category,
            offset=offset,
            limit=per_page,
        )
        return {
            "reports": [self._serialize_admin_report_summary(report) for report in rows],
            **build_pagination_meta(total=total, page=page, per_page=per_page),
        }

    def get_report_for_super_admin(self, report_id: int) -> dict:
        report = self.reports.get_with_relations(report_id)
        if not report:
            raise NotFoundError(Messages.REPORT_NOT_FOUND)
        if report.status == ReportStatus.UNREAD.value:
            report.status = ReportStatus.IN_REVIEW.value
            db.session.commit()
        return self._serialize_admin_report_detail(report)

    def update_report_status(self, report_id: int, *, status: str) -> dict:
        report = self.reports.get_by_id(report_id)
        if not report:
            raise NotFoundError(Messages.REPORT_NOT_FOUND)
        report.status = status
        db.session.commit()
        return {
            "message": Messages.REPORT_STATUS_UPDATED_SUCCESSFULLY,
            "report": {
                "report_id": report.id,
                "status": report.status,
            },
        }

    def _resolve_workspace_context(
        self, actor_user: User, workspace_id: int | None
    ) -> int | None:
        if workspace_id is None:
            return None
        membership = self.reports.get_active_membership_for_user_workspace(
            actor_user.id, workspace_id
        )
        if not membership:
            raise ForbiddenError(Messages.NOT_AN_ACTIVE_MEMBER_OF_THIS_WORKSPACE)
        return workspace_id

    def _serialize_user_report_summary(self, report: Report) -> dict:
        return {
            "report_id": report.id,
            "title": report.title,
            "category": report.category,
            "status": report.status,
            "created_at": report.created_at.isoformat()
            if report.created_at
            else None,
        }

    def _serialize_user_report_detail(self, report: Report) -> dict:
        return {
            "report_id": report.id,
            "title": report.title,
            "description": report.description,
            "category": report.category,
            "status": report.status,
            "created_at": report.created_at.isoformat()
            if report.created_at
            else None,
            "updated_at": report.updated_at.isoformat()
            if report.updated_at
            else None,
        }

    def _serialize_admin_report_summary(self, report: Report) -> dict:
        reporter = report.created_by
        return {
            "report_id": report.id,
            "title": report.title,
            "category": report.category,
            "status": report.status,
            "created_at": report.created_at.isoformat()
            if report.created_at
            else None,
            "reporter": {
                "user_id": reporter.id if reporter else None,
                "full_name": reporter.full_name if reporter else None,
                "email": reporter.email if reporter else None,
            },
        }

    def _serialize_admin_report_detail(self, report: Report) -> dict:
        reporter = report.created_by
        membership = self.reports.get_reporter_membership(report)
        return {
            "report_id": report.id,
            "title": report.title,
            "description": report.description,
            "category": report.category,
            "status": report.status,
            "created_at": report.created_at.isoformat()
            if report.created_at
            else None,
            "updated_at": report.updated_at.isoformat()
            if report.updated_at
            else None,
            "reporter": {
                "user_id": reporter.id if reporter else None,
                "full_name": reporter.full_name if reporter else None,
                "email": reporter.email if reporter else None,
                "role": self._resolve_reporter_role(reporter, membership),
                "workspace_name": report.workspace.name if report.workspace else None,
            },
        }

    def _resolve_reporter_role(self, reporter: User | None, membership) -> str | None:
        if membership:
            return membership.role
        if reporter and reporter.is_superadmin:
            return "SUPER_ADMIN"
        return None
