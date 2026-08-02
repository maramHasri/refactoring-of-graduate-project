"""Institution Analytics Dashboard — workspace owner only."""

from __future__ import annotations

from datetime import datetime, timedelta

from models import Membership, Workspace
from repositories.institution_analytics_repository import (
    AnalyticsScope,
    InstitutionAnalyticsRepository,
)
from repositories.subject_repository import SubjectRepository
from repositories.workspace_repository import MembershipRepository, WorkspaceRepository
from service.exceptions import ForbiddenError, NotFoundError, ValidationError
from utils.app_timezone import format_local_datetime, local_timezone_now
from utils.enums import MembershipRole, WorkspaceKind
from utils.messages import Messages
from utils.rbac import is_workspace_owner

DEFAULT_RANGE_DAYS = 30
INACTIVE_DAYS = 30


class InstitutionAnalyticsService:
    def __init__(self):
        self.workspaces = WorkspaceRepository()
        self.memberships = MembershipRepository()
        self.subjects = SubjectRepository()
        self.analytics = InstitutionAnalyticsRepository()

    def get_analytics(
        self,
        workspace_id: int,
        actor_membership: Membership,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        subject_id: int | None = None,
        teacher_membership_id: int | None = None,
    ) -> dict:
        workspace = self._ensure_owner_access(workspace_id, actor_membership)
        now = local_timezone_now()
        date_from, date_to = self._resolve_date_range(date_from, date_to, now)
        prev_from, prev_to = self._previous_range(date_from, date_to)

        self._validate_optional_filters(
            workspace.id, subject_id=subject_id, teacher_membership_id=teacher_membership_id
        )

        current = AnalyticsScope(
            workspace_id=workspace.id,
            date_from=date_from,
            date_to=date_to,
            subject_id=subject_id,
            teacher_membership_id=teacher_membership_id,
        )
        previous = AnalyticsScope(
            workspace_id=workspace.id,
            date_from=prev_from,
            date_to=prev_to,
            subject_id=subject_id,
            teacher_membership_id=teacher_membership_id,
        )

        overview = self._build_overview(current, previous)
        pass_fail = self._build_pass_fail(current)
        best, weakest = self.analytics.subject_score_extremes(current, limit=3)
        inactive_since = now - timedelta(days=INACTIVE_DAYS)
        inactive = self._build_inactive_students(workspace.id, inactive_since, now)

        return {
            "success": True,
            "filters": {
                "date_from": format_local_datetime(date_from),
                "date_to": format_local_datetime(date_to),
                "subject_id": subject_id,
                "teacher_membership_id": teacher_membership_id,
            },
            "overview": overview,
            "pass_fail": pass_fail,
            "monthly_average_scores": self.analytics.monthly_average_scores(current),
            "most_engaged_subjects": self.analytics.most_engaged_subjects(current),
            "best_subjects": best,
            "weakest_subjects": weakest,
            "teacher_activity": self.analytics.teacher_activity(current),
            "top_students": self.analytics.top_students(current, limit=10),
            "inactive_students": inactive,
            "problematic_exams": self.analytics.problematic_exams(current, limit=10),
        }

    def _ensure_owner_access(
        self, workspace_id: int, actor_membership: Membership
    ) -> Workspace:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)
        if workspace.kind != WorkspaceKind.INSTITUTION.value:
            raise ForbiddenError(
                Messages.THIS_ENDPOINT_IS_ONLY_AVAILABLE_FOR_INSTITUTION_WORKSPACES
            )
        if not is_workspace_owner(workspace, actor_membership):
            raise ForbiddenError(
                Messages.ONLY_THE_WORKSPACE_OWNER_CAN_VIEW_INSTITUTION_ANALYTICS
            )
        return workspace

    def _validate_optional_filters(
        self,
        workspace_id: int,
        *,
        subject_id: int | None,
        teacher_membership_id: int | None,
    ) -> None:
        if subject_id is not None:
            subject = self.subjects.get_by_id(subject_id)
            if (
                subject is None
                or subject.workspace_id != workspace_id
                or subject.deleted_at is not None
            ):
                raise ValidationError(Messages.SUBJECT_NOT_FOUND_IN_THIS_WORKSPACE)

        if teacher_membership_id is not None:
            membership = self.memberships.get_by_id(teacher_membership_id)
            if (
                membership is None
                or membership.workspace_id != workspace_id
                or membership.role != MembershipRole.TEACHER.value
            ):
                raise ValidationError(Messages.MEMBERSHIP_NOT_FOUND_IN_THIS_WORKSPACE)

    @staticmethod
    def _resolve_date_range(
        date_from: datetime | None,
        date_to: datetime | None,
        now: datetime,
    ) -> tuple[datetime, datetime]:
        if date_from is None and date_to is None:
            date_to = now
            date_from = now - timedelta(days=DEFAULT_RANGE_DAYS)
        elif date_from is None:
            date_from = date_to - timedelta(days=DEFAULT_RANGE_DAYS)
        elif date_to is None:
            date_to = now

        if date_from > date_to:
            raise ValidationError(
                Messages.DATE_FROM_MUST_BE_BEFORE_OR_EQUAL_TO_DATE_TO
            )
        return date_from, date_to

    @staticmethod
    def _previous_range(
        date_from: datetime, date_to: datetime
    ) -> tuple[datetime, datetime]:
        delta = date_to - date_from
        prev_to = date_from - timedelta(microseconds=1)
        prev_from = prev_to - delta
        return prev_from, prev_to

    @staticmethod
    def change_percentage(current: float, previous: float) -> float:
        if previous == 0:
            if current == 0:
                return 0.0
            return 100.0
        return round(((current - previous) / abs(previous)) * 100, 2)

    @staticmethod
    def _metric(value, previous_value) -> dict:
        return {
            "value": value,
            "change_percentage": InstitutionAnalyticsService.change_percentage(
                float(value or 0), float(previous_value or 0)
            ),
        }

    def _build_overview(
        self, current: AnalyticsScope, previous: AnalyticsScope
    ) -> dict:
        members = self.analytics.count_active_members_by_role(current.workspace_id)
        total_students = members["students"]
        total_teachers = members["teachers"]

        students_joined = self.analytics.count_members_joined_in_range(
            current.workspace_id,
            MembershipRole.STUDENT.value,
            current.date_from,
            current.date_to,
        )
        students_joined_prev = self.analytics.count_members_joined_in_range(
            previous.workspace_id,
            MembershipRole.STUDENT.value,
            previous.date_from,
            previous.date_to,
        )
        teachers_joined = self.analytics.count_members_joined_in_range(
            current.workspace_id,
            MembershipRole.TEACHER.value,
            current.date_from,
            current.date_to,
        )
        teachers_joined_prev = self.analytics.count_members_joined_in_range(
            previous.workspace_id,
            MembershipRole.TEACHER.value,
            previous.date_from,
            previous.date_to,
        )

        total_tests = self.analytics.count_tests(current)
        tests_created = self.analytics.count_tests_created_in_range(current)
        tests_created_prev = self.analytics.count_tests_created_in_range(previous)

        attempts = self.analytics.count_graded_attempts(current)
        attempts_prev = self.analytics.count_graded_attempts(previous)

        avg = self.analytics.average_graded_percentage(current)
        avg_prev = self.analytics.average_graded_percentage(previous)

        active = self.analytics.count_active_students(
            current.workspace_id, current.date_from, current.date_to
        )
        active_prev = self.analytics.count_active_students(
            previous.workspace_id, previous.date_from, previous.date_to
        )

        return {
            "total_students": {
                "value": total_students,
                "change_percentage": self.change_percentage(
                    students_joined, students_joined_prev
                ),
            },
            "total_teachers": {
                "value": total_teachers,
                "change_percentage": self.change_percentage(
                    teachers_joined, teachers_joined_prev
                ),
            },
            "total_tests": {
                "value": total_tests,
                "change_percentage": self.change_percentage(
                    tests_created, tests_created_prev
                ),
            },
            "total_attempts": self._metric(attempts, attempts_prev),
            "institution_average_score": self._metric(avg, avg_prev),
            "active_students": self._metric(active, active_prev),
        }

    def _build_pass_fail(self, scope: AnalyticsScope) -> dict:
        counts = self.analytics.pass_fail_counts(scope)
        total = counts["total"]
        passed = counts["passed"]
        failed = counts["failed"]
        if total == 0:
            pass_rate = 0.0
            fail_rate = 0.0
        else:
            pass_rate = round((passed / total) * 100, 2)
            fail_rate = round((failed / total) * 100, 2)
        return {
            "pass_rate": pass_rate,
            "fail_rate": fail_rate,
            "passed_attempts": passed,
            "failed_attempts": failed,
        }

    def _build_inactive_students(
        self, workspace_id: int, inactive_since: datetime, now: datetime
    ) -> list[dict]:
        rows = self.analytics.inactive_students(
            workspace_id, inactive_since=inactive_since
        )
        result = []
        for row in rows:
            last_at = row["last_activity_at"]
            reference = last_at or row.get("joined_at")
            if reference is None:
                days_inactive = INACTIVE_DAYS
            else:
                days_inactive = max(0, int((now - reference).total_seconds() // 86400))
            result.append(
                {
                    "student_membership_id": row["student_membership_id"],
                    "student_name": row["student_name"],
                    "days_inactive": days_inactive,
                    "last_activity_at": format_local_datetime(last_at),
                }
            )
        return result
