from datetime import datetime, timedelta, timezone

from sqlalchemy import distinct, func

from models import (
    Membership,
    ProctoringViolation,
    Question,
    Subject,
    Test,
    TestAttempt,
    Topic,
    User,
    Workspace,
)
from repositories.base_repository import BaseRepository
from utils.db import db
from utils.enums import MembershipRole, ProctoringViolationStatus, TestAttemptStatus, WorkspaceKind


class SuperAdminDashboardRepository(BaseRepository):
    def build_dashboard(self) -> dict:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_30_start = now - timedelta(days=30)

        users = self._users_section(day_start, week_start, month_30_start, month_start)
        organizations = self._organizations_section(month_start)
        content = self._content_section()
        tests = self._tests_section(day_start, week_start, month_30_start)
        reports = self._reports_section()
        return {
            "users": users,
            "organizations": organizations,
            "content": content,
            "tests": tests,
            "reports": reports,
        }

    def _users_section(
        self,
        day_start: datetime,
        week_start: datetime,
        month_30_start: datetime,
        month_start: datetime,
    ) -> dict:
        total = db.session.execute(
            db.select(func.count(User.id))
        ).scalar_one() or 0

        students = self._count_distinct_users_by_role(MembershipRole.STUDENT.value)
        teachers = self._count_distinct_users_by_role(MembershipRole.TEACHER.value)
        organization_admins = db.session.execute(
            db.select(func.count(distinct(Membership.user_id)))
            .select_from(Membership)
            .join(Workspace, Workspace.id == Membership.workspace_id)
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.role == MembershipRole.ADMIN.value,
                Membership.status == "ACTIVE",
                Workspace.kind == WorkspaceKind.INSTITUTION.value,
                User.is_superadmin.is_(False),
            )
        ).scalar_one() or 0
        super_admins = db.session.execute(
            db.select(func.count(User.id)).where(User.is_superadmin.is_(True))
        ).scalar_one() or 0

        active_today = db.session.execute(
            db.select(func.count(User.id)).where(User.last_login_at >= day_start)
        ).scalar_one() or 0
        active_week = db.session.execute(
            db.select(func.count(User.id)).where(User.last_login_at >= week_start)
        ).scalar_one() or 0
        active_month = db.session.execute(
            db.select(func.count(User.id)).where(User.last_login_at >= month_30_start)
        ).scalar_one() or 0
        new_this_month = db.session.execute(
            db.select(func.count(User.id)).where(User.created_at >= month_start)
        ).scalar_one() or 0

        return {
            "total": int(total),
            "students": int(students),
            "teachers": int(teachers),
            "organization_admins": int(organization_admins),
            "super_admins": int(super_admins),
            "active_today": int(active_today),
            "active_week": int(active_week),
            "active_month": int(active_month),
            "new_this_month": int(new_this_month),
        }

    def _organizations_section(self, month_start: datetime) -> dict:
        total = db.session.execute(
            db.select(func.count(Workspace.id)).where(
                Workspace.kind == WorkspaceKind.INSTITUTION.value
            )
        ).scalar_one() or 0
        active = db.session.execute(
            db.select(func.count(Workspace.id)).where(
                Workspace.kind == WorkspaceKind.INSTITUTION.value,
                Workspace.status == "ACTIVE",
            )
        ).scalar_one() or 0
        suspended = db.session.execute(
            db.select(func.count(Workspace.id)).where(
                Workspace.kind == WorkspaceKind.INSTITUTION.value,
                Workspace.status == "SUSPENDED",
            )
        ).scalar_one() or 0
        new_this_month = db.session.execute(
            db.select(func.count(Workspace.id)).where(
                Workspace.kind == WorkspaceKind.INSTITUTION.value,
                Workspace.created_at >= month_start,
            )
        ).scalar_one() or 0

        active_users_sq = (
            db.select(
                Membership.workspace_id.label("workspace_id"),
                func.count(distinct(Membership.user_id)).label("active_users"),
            )
            .where(Membership.status == "ACTIVE")
            .group_by(Membership.workspace_id)
            .subquery()
        )
        tests_sq = (
            db.select(
                Membership.workspace_id.label("workspace_id"),
                func.count(Test.id).label("tests_count"),
            )
            .select_from(Test)
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .group_by(Membership.workspace_id)
            .subquery()
        )
        attempts_sq = (
            db.select(
                Membership.workspace_id.label("workspace_id"),
                func.count(TestAttempt.id).label("attempts_count"),
            )
            .select_from(TestAttempt)
            .join(Test, Test.id == TestAttempt.test_id)
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .group_by(Membership.workspace_id)
            .subquery()
        )

        rows = db.session.execute(
            db.select(
                Workspace.id,
                Workspace.name,
                func.coalesce(active_users_sq.c.active_users, 0),
                func.coalesce(tests_sq.c.tests_count, 0),
                func.coalesce(attempts_sq.c.attempts_count, 0),
            )
            .outerjoin(active_users_sq, active_users_sq.c.workspace_id == Workspace.id)
            .outerjoin(tests_sq, tests_sq.c.workspace_id == Workspace.id)
            .outerjoin(attempts_sq, attempts_sq.c.workspace_id == Workspace.id)
            .where(Workspace.kind == WorkspaceKind.INSTITUTION.value)
            .order_by(
                (
                    func.coalesce(active_users_sq.c.active_users, 0)
                    + func.coalesce(attempts_sq.c.attempts_count, 0)
                    + func.coalesce(tests_sq.c.tests_count, 0)
                ).desc(),
                Workspace.id,
            )
            .limit(5)
        ).all()
        most_active = [
            {
                "organization_id": int(wid),
                "organization_name": wname,
                "active_users": int(active_users or 0),
                "tests_count": int(tests_count or 0),
                "attempts_count": int(attempts_count or 0),
            }
            for wid, wname, active_users, tests_count, attempts_count in rows
        ]

        return {
            "total": int(total),
            "active": int(active),
            "suspended": int(suspended),
            "new_this_month": int(new_this_month),
            "most_active": most_active,
        }

    def _content_section(self) -> dict:
        subjects = db.session.execute(
            db.select(func.count(Subject.id)).where(Subject.deleted_at.is_(None))
        ).scalar_one() or 0
        topics = db.session.execute(
            db.select(func.count(Topic.id))
        ).scalar_one() or 0
        questions = db.session.execute(
            db.select(func.count(Question.id))
        ).scalar_one() or 0
        tests = db.session.execute(
            db.select(func.count(Test.id))
        ).scalar_one() or 0
        return {
            "subjects": int(subjects),
            "topics": int(topics),
            "questions": int(questions),
            "tests": int(tests),
        }

    def _tests_section(
        self,
        day_start: datetime,
        week_start: datetime,
        month_30_start: datetime,
    ) -> dict:
        total_tests = db.session.execute(
            db.select(func.count(Test.id))
        ).scalar_one() or 0
        total_attempts = db.session.execute(
            db.select(func.count(TestAttempt.id))
        ).scalar_one() or 0
        attempts_today = db.session.execute(
            db.select(func.count(TestAttempt.id)).where(TestAttempt.started_at >= day_start)
        ).scalar_one() or 0
        attempts_week = db.session.execute(
            db.select(func.count(TestAttempt.id)).where(TestAttempt.started_at >= week_start)
        ).scalar_one() or 0
        attempts_month = db.session.execute(
            db.select(func.count(TestAttempt.id)).where(
                TestAttempt.started_at >= month_30_start
            )
        ).scalar_one() or 0
        average_score = db.session.execute(
            db.select(func.avg(TestAttempt.final_score)).where(
                TestAttempt.status == TestAttemptStatus.GRADED.value,
                TestAttempt.final_score.is_not(None),
            )
        ).scalar()
        return {
            "total_tests": int(total_tests),
            "total_attempts": int(total_attempts),
            "attempts_today": int(attempts_today),
            "attempts_week": int(attempts_week),
            "attempts_month": int(attempts_month),
            "average_score": round(float(average_score or 0.0), 2),
        }

    def _reports_section(self) -> dict:
        total = db.session.execute(
            db.select(func.count(ProctoringViolation.id))
        ).scalar_one() or 0
        grouped = dict(
            db.session.execute(
                db.select(
                    ProctoringViolation.status,
                    func.count(ProctoringViolation.id),
                ).group_by(ProctoringViolation.status)
            ).all()
        )
        # Mapping current system statuses to dashboard semantics.
        return {
            "total": int(total),
            "pending": int(grouped.get(ProctoringViolationStatus.OPEN.value, 0)),
            "under_review": int(grouped.get(ProctoringViolationStatus.REVIEWED.value, 0)),
            "resolved": int(grouped.get(ProctoringViolationStatus.CONFIRMED.value, 0)),
            "rejected": int(grouped.get(ProctoringViolationStatus.DISMISSED.value, 0)),
        }

    def _count_distinct_users_by_role(self, role: str) -> int:
        return (
            db.session.execute(
                db.select(func.count(distinct(Membership.user_id))).where(
                    Membership.role == role,
                    Membership.status == "ACTIVE",
                )
            ).scalar_one()
            or 0
        )
