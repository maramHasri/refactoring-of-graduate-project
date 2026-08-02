"""Aggregated SQL for the Institution Analytics Dashboard (owner-only).

All attempt-based academic metrics filter on ``TestAttempt.graded_at``.
Workspace isolation is enforced via ``Membership.workspace_id`` on the test creator.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, case, func, or_, select

from models import (
    Membership,
    ProctoringSession,
    ProctoringViolation,
    Subject,
    SubjectMembership,
    Test,
    TestAttempt,
    TestQuestion,
    TestStudentAssignment,
    User,
)
from repositories.base_repository import BaseRepository
from service.proctoring_risk_service import ProctoringRiskService
from service.student_analytics_service import StudentAnalyticsService
from utils.db import db
from utils.enums import (
    AttemptSubmissionSource,
    MembershipRole,
    MembershipStatus,
    ProctoringViolationStatus,
    SubjectMembershipStatus,
    SubjectRole,
    TestAttemptStatus,
)


@dataclass(frozen=True)
class AnalyticsScope:
    workspace_id: int
    date_from: datetime
    date_to: datetime
    subject_id: int | None = None
    teacher_membership_id: int | None = None


class InstitutionAnalyticsRepository(BaseRepository):
    """Few large aggregations — no per-row / per-entity queries in loops."""

    # --- shared filters -------------------------------------------------

    def _test_scope_filters(self, scope: AnalyticsScope) -> list:
        filters = [
            Membership.workspace_id == scope.workspace_id,
            Test.archived_at.is_(None),
        ]
        if scope.subject_id is not None:
            filters.append(Test.subject_id == scope.subject_id)
        if scope.teacher_membership_id is not None:
            filters.append(
                Test.created_by_membership_id == scope.teacher_membership_id
            )
        return filters

    def _graded_in_range_filters(self, scope: AnalyticsScope) -> list:
        return [
            *self._test_scope_filters(scope),
            TestAttempt.status == TestAttemptStatus.GRADED.value,
            TestAttempt.percentage.is_not(None),
            TestAttempt.graded_at.is_not(None),
            TestAttempt.graded_at >= scope.date_from,
            TestAttempt.graded_at <= scope.date_to,
        ]

    @staticmethod
    def _as_float(value) -> float:
        if value is None:
            return 0.0
        if isinstance(value, Decimal):
            return float(value)
        return float(value)

    @staticmethod
    def _round(value, digits: int = 2) -> float:
        return round(InstitutionAnalyticsRepository._as_float(value), digits)

    # --- overview -------------------------------------------------------

    def count_active_members_by_role(self, workspace_id: int) -> dict[str, int]:
        rows = db.session.execute(
            select(Membership.role, func.count(Membership.id))
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.workspace_id == workspace_id,
                Membership.status == MembershipStatus.ACTIVE.value,
                User.deleted_at.is_(None),
                Membership.role.in_(
                    [MembershipRole.TEACHER.value, MembershipRole.STUDENT.value]
                ),
            )
            .group_by(Membership.role)
        ).all()
        counts = {role: int(count) for role, count in rows}
        return {
            "teachers": counts.get(MembershipRole.TEACHER.value, 0),
            "students": counts.get(MembershipRole.STUDENT.value, 0),
        }

    def count_members_joined_in_range(
        self, workspace_id: int, role: str, date_from: datetime, date_to: datetime
    ) -> int:
        return int(
            db.session.execute(
                select(func.count(Membership.id))
                .join(User, User.id == Membership.user_id)
                .where(
                    Membership.workspace_id == workspace_id,
                    Membership.status == MembershipStatus.ACTIVE.value,
                    Membership.role == role,
                    User.deleted_at.is_(None),
                    Membership.joined_at >= date_from,
                    Membership.joined_at <= date_to,
                )
            ).scalar_one()
            or 0
        )

    def count_tests(self, scope: AnalyticsScope) -> int:
        return int(
            db.session.execute(
                select(func.count(Test.id))
                .select_from(Test)
                .join(Membership, Membership.id == Test.created_by_membership_id)
                .where(*self._test_scope_filters(scope))
            ).scalar_one()
            or 0
        )

    def count_tests_created_in_range(self, scope: AnalyticsScope) -> int:
        return int(
            db.session.execute(
                select(func.count(Test.id))
                .select_from(Test)
                .join(Membership, Membership.id == Test.created_by_membership_id)
                .where(
                    *self._test_scope_filters(scope),
                    Test.created_at >= scope.date_from,
                    Test.created_at <= scope.date_to,
                )
            ).scalar_one()
            or 0
        )

    def count_graded_attempts(self, scope: AnalyticsScope) -> int:
        return int(
            db.session.execute(
                select(func.count(TestAttempt.id))
                .select_from(TestAttempt)
                .join(Test, Test.id == TestAttempt.test_id)
                .join(Membership, Membership.id == Test.created_by_membership_id)
                .where(*self._graded_in_range_filters(scope))
            ).scalar_one()
            or 0
        )

    def average_graded_percentage(self, scope: AnalyticsScope) -> float:
        value = db.session.execute(
            select(func.avg(TestAttempt.percentage))
            .select_from(TestAttempt)
            .join(Test, Test.id == TestAttempt.test_id)
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .where(*self._graded_in_range_filters(scope))
        ).scalar()
        return self._round(value) if value is not None else 0.0

    def _student_effective_activity_subquery(self, workspace_id: int):
        attempt_activity = (
            select(
                TestAttempt.user_id.label("user_id"),
                func.max(TestAttempt.last_activity_at).label("attempt_activity_at"),
            )
            .join(Membership, Membership.id == TestAttempt.student_membership_id)
            .where(Membership.workspace_id == workspace_id)
            .group_by(TestAttempt.user_id)
            .subquery()
        )
        return attempt_activity, func.coalesce(
            attempt_activity.c.attempt_activity_at,
            User.last_login_at,
        )

    def count_active_students(
        self, workspace_id: int, date_from: datetime, date_to: datetime
    ) -> int:
        attempt_activity, effective = self._student_effective_activity_subquery(
            workspace_id
        )
        return int(
            db.session.execute(
                select(func.count(Membership.id))
                .join(User, User.id == Membership.user_id)
                .outerjoin(
                    attempt_activity, attempt_activity.c.user_id == User.id
                )
                .where(
                    Membership.workspace_id == workspace_id,
                    Membership.status == MembershipStatus.ACTIVE.value,
                    Membership.role == MembershipRole.STUDENT.value,
                    User.deleted_at.is_(None),
                    effective.is_not(None),
                    effective >= date_from,
                    effective <= date_to,
                )
            ).scalar_one()
            or 0
        )

    # --- pass / fail ----------------------------------------------------

    def pass_fail_counts(self, scope: AnalyticsScope) -> dict[str, int]:
        passed_flag = StudentAnalyticsService.pass_sql_expression(
            TestAttempt.final_score, Test.passing_score
        )
        row = db.session.execute(
            select(
                func.count(TestAttempt.id).label("total"),
                func.coalesce(func.sum(passed_flag), 0).label("passed"),
            )
            .select_from(TestAttempt)
            .join(Test, Test.id == TestAttempt.test_id)
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .where(*self._graded_in_range_filters(scope))
        ).one()
        total = int(row.total or 0)
        passed = int(row.passed or 0)
        return {"total": total, "passed": passed, "failed": total - passed}

    # --- monthly trend --------------------------------------------------

    def monthly_average_scores(self, scope: AnalyticsScope) -> list[dict]:
        month_bucket = func.date_trunc("month", TestAttempt.graded_at).label("month")
        rows = db.session.execute(
            select(
                month_bucket,
                func.avg(TestAttempt.percentage).label("average_score"),
            )
            .select_from(TestAttempt)
            .join(Test, Test.id == TestAttempt.test_id)
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .where(*self._graded_in_range_filters(scope))
            .group_by(month_bucket)
            .order_by(month_bucket.asc())
        ).all()
        data: list[dict] = []
        for month, average_score in rows:
            if month is None:
                continue
            period = month.strftime("%Y-%m") if hasattr(month, "strftime") else str(month)[:7]
            data.append(
                {
                    "period": period,
                    "average_score": self._round(average_score),
                }
            )
        return data

    # --- subjects -------------------------------------------------------

    def most_engaged_subjects(self, scope: AnalyticsScope, *, limit: int = 10) -> list[dict]:
        student_counts = (
            select(
                SubjectMembership.subject_id.label("subject_id"),
                func.count(SubjectMembership.id).label("students_count"),
            )
            .where(
                SubjectMembership.deleted_at.is_(None),
                SubjectMembership.status == SubjectMembershipStatus.ACTIVE.value,
                SubjectMembership.subject_role == SubjectRole.STUDENT.value,
            )
            .group_by(SubjectMembership.subject_id)
            .subquery()
        )
        teacher_counts = (
            select(
                SubjectMembership.subject_id.label("subject_id"),
                func.count(SubjectMembership.id).label("teachers_count"),
            )
            .where(
                SubjectMembership.deleted_at.is_(None),
                SubjectMembership.status == SubjectMembershipStatus.ACTIVE.value,
                SubjectMembership.subject_role == SubjectRole.TEACHER.value,
            )
            .group_by(SubjectMembership.subject_id)
            .subquery()
        )
        test_counts = (
            select(
                Test.subject_id.label("subject_id"),
                func.count(Test.id).label("tests_count"),
            )
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .where(*self._test_scope_filters(scope), Test.subject_id.is_not(None))
            .group_by(Test.subject_id)
            .subquery()
        )
        avg_scores = (
            select(
                Test.subject_id.label("subject_id"),
                func.avg(TestAttempt.percentage).label("average_score"),
            )
            .select_from(TestAttempt)
            .join(Test, Test.id == TestAttempt.test_id)
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .where(
                *self._graded_in_range_filters(scope),
                Test.subject_id.is_not(None),
            )
            .group_by(Test.subject_id)
            .subquery()
        )

        students = func.coalesce(student_counts.c.students_count, 0)
        teachers = func.coalesce(teacher_counts.c.teachers_count, 0)
        tests = func.coalesce(test_counts.c.tests_count, 0)
        activity_score = (0.6 * students) + (0.2 * teachers) + (0.2 * tests)

        subject_filters = [
            Subject.workspace_id == scope.workspace_id,
            Subject.deleted_at.is_(None),
        ]
        if scope.subject_id is not None:
            subject_filters.append(Subject.id == scope.subject_id)

        rows = db.session.execute(
            select(
                Subject.id,
                Subject.name,
                students.label("students_count"),
                teachers.label("teachers_count"),
                tests.label("tests_count"),
                avg_scores.c.average_score,
                activity_score.label("activity_score"),
            )
            .outerjoin(student_counts, student_counts.c.subject_id == Subject.id)
            .outerjoin(teacher_counts, teacher_counts.c.subject_id == Subject.id)
            .outerjoin(test_counts, test_counts.c.subject_id == Subject.id)
            .outerjoin(avg_scores, avg_scores.c.subject_id == Subject.id)
            .where(*subject_filters)
            .order_by(activity_score.desc(), Subject.name.asc(), Subject.id.asc())
            .limit(limit)
        ).all()

        return [
            {
                "subject_id": int(row.id),
                "subject_name": row.name,
                "students_count": int(row.students_count or 0),
                "teachers_count": int(row.teachers_count or 0),
                "tests_count": int(row.tests_count or 0),
                "average_score": self._round(row.average_score)
                if row.average_score is not None
                else None,
                "activity_score": self._round(row.activity_score),
            }
            for row in rows
        ]

    def subject_score_extremes(
        self, scope: AnalyticsScope, *, limit: int = 3
    ) -> tuple[list[dict], list[dict]]:
        rows = db.session.execute(
            select(
                Subject.id,
                Subject.name,
                func.avg(TestAttempt.percentage).label("average_score"),
                func.count(TestAttempt.id).label("attempt_count"),
            )
            .select_from(TestAttempt)
            .join(Test, Test.id == TestAttempt.test_id)
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .join(Subject, Subject.id == Test.subject_id)
            .where(
                *self._graded_in_range_filters(scope),
                Subject.workspace_id == scope.workspace_id,
                Subject.deleted_at.is_(None),
            )
            .group_by(Subject.id, Subject.name)
            .having(func.count(TestAttempt.id) > 0)
        ).all()

        ranked = [
            {
                "subject_id": int(row.id),
                "subject_name": row.name,
                "average_score": self._round(row.average_score),
                "attempt_count": int(row.attempt_count or 0),
            }
            for row in rows
        ]
        best = sorted(
            ranked,
            key=lambda item: (item["average_score"], item["attempt_count"]),
            reverse=True,
        )[:limit]
        weakest = sorted(
            ranked,
            key=lambda item: (item["average_score"], -item["attempt_count"]),
        )[:limit]
        return best, weakest

    # --- teachers -------------------------------------------------------

    def teacher_activity(self, scope: AnalyticsScope) -> list[dict]:
        creator = Membership
        teacher_user = User

        tests_created = (
            select(
                Test.created_by_membership_id.label("teacher_membership_id"),
                func.count(Test.id).label("tests_created"),
            )
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .where(*self._test_scope_filters(scope))
            .group_by(Test.created_by_membership_id)
            .subquery()
        )

        targeted = (
            select(
                Test.created_by_membership_id.label("teacher_membership_id"),
                func.count(func.distinct(TestStudentAssignment.student_membership_id)).label(
                    "targeted_students"
                ),
            )
            .select_from(TestStudentAssignment)
            .join(Test, Test.id == TestStudentAssignment.test_id)
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .where(*self._test_scope_filters(scope))
            .group_by(Test.created_by_membership_id)
            .subquery()
        )

        assignment_rows = (
            select(
                Test.created_by_membership_id.label("teacher_membership_id"),
                func.count(TestStudentAssignment.id).label("assignment_count"),
            )
            .select_from(TestStudentAssignment)
            .join(Test, Test.id == TestStudentAssignment.test_id)
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .where(*self._test_scope_filters(scope))
            .group_by(Test.created_by_membership_id)
            .subquery()
        )

        completed = (
            select(
                Test.created_by_membership_id.label("teacher_membership_id"),
                func.count(TestAttempt.id).label("completed_attempts"),
            )
            .select_from(TestAttempt)
            .join(Test, Test.id == TestAttempt.test_id)
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .where(
                *self._test_scope_filters(scope),
                TestAttempt.status.in_(
                    [
                        TestAttemptStatus.SUBMITTED.value,
                        TestAttemptStatus.GRADED.value,
                    ]
                ),
                or_(
                    and_(
                        TestAttempt.graded_at.is_not(None),
                        TestAttempt.graded_at >= scope.date_from,
                        TestAttempt.graded_at <= scope.date_to,
                    ),
                    and_(
                        TestAttempt.submitted_at.is_not(None),
                        TestAttempt.submitted_at >= scope.date_from,
                        TestAttempt.submitted_at <= scope.date_to,
                    ),
                ),
            )
            .group_by(Test.created_by_membership_id)
            .subquery()
        )

        avg_scores = (
            select(
                Test.created_by_membership_id.label("teacher_membership_id"),
                func.avg(TestAttempt.percentage).label("average_student_score"),
            )
            .select_from(TestAttempt)
            .join(Test, Test.id == TestAttempt.test_id)
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .where(*self._graded_in_range_filters(scope))
            .group_by(Test.created_by_membership_id)
            .subquery()
        )

        teacher_filters = [
            creator.workspace_id == scope.workspace_id,
            creator.status == MembershipStatus.ACTIVE.value,
            creator.role == MembershipRole.TEACHER.value,
            teacher_user.deleted_at.is_(None),
        ]
        if scope.teacher_membership_id is not None:
            teacher_filters.append(creator.id == scope.teacher_membership_id)

        assignment_count = func.coalesce(assignment_rows.c.assignment_count, 0)
        completed_count = func.coalesce(completed.c.completed_attempts, 0)
        completion_rate = case(
            (assignment_count <= 0, 0.0),
            else_=func.least(
                100.0,
                (completed_count * 100.0) / assignment_count,
            ),
        )

        rows = db.session.execute(
            select(
                creator.id.label("teacher_membership_id"),
                teacher_user.full_name.label("teacher_name"),
                func.coalesce(tests_created.c.tests_created, 0).label("tests_created"),
                func.coalesce(targeted.c.targeted_students, 0).label("targeted_students"),
                avg_scores.c.average_student_score,
                completion_rate.label("completion_rate"),
            )
            .select_from(creator)
            .join(teacher_user, teacher_user.id == creator.user_id)
            .outerjoin(
                tests_created, tests_created.c.teacher_membership_id == creator.id
            )
            .outerjoin(targeted, targeted.c.teacher_membership_id == creator.id)
            .outerjoin(
                assignment_rows, assignment_rows.c.teacher_membership_id == creator.id
            )
            .outerjoin(completed, completed.c.teacher_membership_id == creator.id)
            .outerjoin(avg_scores, avg_scores.c.teacher_membership_id == creator.id)
            .where(*teacher_filters)
            .order_by(
                avg_scores.c.average_student_score.desc().nullslast(),
                teacher_user.full_name.asc(),
                creator.id.asc(),
            )
        ).all()

        return [
            {
                "teacher_membership_id": int(row.teacher_membership_id),
                "teacher_name": row.teacher_name,
                "tests_created": int(row.tests_created or 0),
                "targeted_students": int(row.targeted_students or 0),
                "average_student_score": self._round(row.average_student_score)
                if row.average_student_score is not None
                else None,
                "completion_rate": self._round(row.completion_rate),
            }
            for row in rows
        ]

    # --- students -------------------------------------------------------

    def top_students(self, scope: AnalyticsScope, *, limit: int = 10) -> list[dict]:
        student_m = Membership
        rows = db.session.execute(
            select(
                student_m.id.label("student_membership_id"),
                User.full_name.label("student_name"),
                User.profile_image_url.label("profile_image"),
                func.avg(TestAttempt.percentage).label("average_score"),
                func.count(TestAttempt.id).label("completed_tests"),
            )
            .select_from(TestAttempt)
            .join(Test, Test.id == TestAttempt.test_id)
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .join(student_m, student_m.id == TestAttempt.student_membership_id)
            .join(User, User.id == student_m.user_id)
            .where(
                *self._graded_in_range_filters(scope),
                student_m.workspace_id == scope.workspace_id,
                student_m.status == MembershipStatus.ACTIVE.value,
                student_m.role == MembershipRole.STUDENT.value,
                User.deleted_at.is_(None),
            )
            .group_by(
                student_m.id,
                User.full_name,
                User.profile_image_url,
            )
            .order_by(
                func.avg(TestAttempt.percentage).desc(),
                func.count(TestAttempt.id).desc(),
                User.full_name.asc(),
            )
            .limit(limit)
        ).all()

        return [
            {
                "student_membership_id": int(row.student_membership_id),
                "student_name": row.student_name,
                "average_score": self._round(row.average_score),
                "completed_tests": int(row.completed_tests or 0),
                "profile_image": row.profile_image,
            }
            for row in rows
        ]

    def inactive_students(
        self, workspace_id: int, *, inactive_since: datetime, limit: int = 50
    ) -> list[dict]:
        attempt_activity, effective = self._student_effective_activity_subquery(
            workspace_id
        )
        rows = db.session.execute(
            select(
                Membership.id.label("student_membership_id"),
                User.full_name.label("student_name"),
                effective.label("last_activity_at"),
                Membership.joined_at.label("joined_at"),
            )
            .join(User, User.id == Membership.user_id)
            .outerjoin(attempt_activity, attempt_activity.c.user_id == User.id)
            .where(
                Membership.workspace_id == workspace_id,
                Membership.status == MembershipStatus.ACTIVE.value,
                Membership.role == MembershipRole.STUDENT.value,
                User.deleted_at.is_(None),
                or_(effective.is_(None), effective < inactive_since),
            )
            .order_by(effective.asc().nullsfirst(), User.full_name.asc())
            .limit(limit)
        ).all()
        return [
            {
                "student_membership_id": int(row.student_membership_id),
                "student_name": row.student_name,
                "last_activity_at": row.last_activity_at,
                "joined_at": row.joined_at,
            }
            for row in rows
        ]

    # --- problematic exams ----------------------------------------------

    def problematic_exams(self, scope: AnalyticsScope, *, limit: int = 10) -> list[dict]:
        """
        Rank exams by composite risk signal.

        ``integrity_reports_count`` = attempts with ``submission_source=PROCTORING_AUTO``.
        There is no persisted Proctoring Report entity; this is the closest
        first-class proctoring integrity signal (not Support ``Report`` rows).

        ``risk_percentage`` uses the same formula as ``ProctoringRiskService``
        applied to per-attempt effective violation scores (SQL aggregation).
        """
        risk = ProctoringRiskService
        q_count = (
            select(
                TestQuestion.test_id.label("test_id"),
                func.count(TestQuestion.id).label("question_count"),
            )
            .group_by(TestQuestion.test_id)
            .subquery()
        )

        # Attempts in window: graded_at or submitted_at (covers auto-terminated)
        attempt_in_window = or_(
            and_(
                TestAttempt.graded_at.is_not(None),
                TestAttempt.graded_at >= scope.date_from,
                TestAttempt.graded_at <= scope.date_to,
            ),
            and_(
                TestAttempt.submitted_at.is_not(None),
                TestAttempt.submitted_at >= scope.date_from,
                TestAttempt.submitted_at <= scope.date_to,
            ),
        )

        violation_sum = (
            select(
                ProctoringSession.test_attempt_id.label("attempt_id"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ProctoringViolation.status
                                != ProctoringViolationStatus.DISMISSED.value,
                                ProctoringViolation.score_contribution,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("effective_score"),
                func.count(
                    case(
                        (
                            ProctoringViolation.status
                            != ProctoringViolationStatus.DISMISSED.value,
                            ProctoringViolation.id,
                        ),
                        else_=None,
                    )
                ).label("violations_count"),
            )
            .select_from(ProctoringSession)
            .outerjoin(
                ProctoringViolation,
                ProctoringViolation.session_id == ProctoringSession.id,
            )
            .where(ProctoringSession.workspace_id == scope.workspace_id)
            .group_by(ProctoringSession.test_attempt_id)
            .subquery()
        )

        question_factor = case(
            (func.coalesce(q_count.c.question_count, 0) <= 0, risk.QUESTION_FACTOR_MIN),
            else_=func.greatest(
                risk.QUESTION_FACTOR_MIN,
                func.least(
                    risk.QUESTION_FACTOR_MAX,
                    func.coalesce(q_count.c.question_count, 0) / float(risk.QUESTION_BASELINE),
                ),
            ),
        )
        # risk% = min(effective/100 * factor * 100, MAX) = min(effective * factor, MAX)
        attempt_risk = func.least(
            risk.MAX_RISK_PERCENTAGE,
            func.coalesce(violation_sum.c.effective_score, 0) * question_factor,
        )

        rows = db.session.execute(
            select(
                Test.id.label("test_id"),
                Test.name.label("test_name"),
                Subject.name.label("subject_name"),
                func.avg(attempt_risk).label("risk_percentage"),
                func.coalesce(func.sum(violation_sum.c.violations_count), 0).label(
                    "violations_count"
                ),
                func.count(
                    case(
                        (
                            TestAttempt.submission_source
                            == AttemptSubmissionSource.PROCTORING_AUTO.value,
                            TestAttempt.id,
                        ),
                        else_=None,
                    )
                ).label("integrity_reports_count"),
                func.avg(
                    case(
                        (
                            and_(
                                TestAttempt.status == TestAttemptStatus.GRADED.value,
                                TestAttempt.percentage.is_not(None),
                            ),
                            TestAttempt.percentage,
                        ),
                        else_=None,
                    )
                ).label("average_score"),
            )
            .select_from(TestAttempt)
            .join(Test, Test.id == TestAttempt.test_id)
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .outerjoin(Subject, Subject.id == Test.subject_id)
            .outerjoin(q_count, q_count.c.test_id == Test.id)
            .outerjoin(
                violation_sum, violation_sum.c.attempt_id == TestAttempt.id
            )
            .where(
                *self._test_scope_filters(scope),
                attempt_in_window,
            )
            .group_by(Test.id, Test.name, Subject.name)
            .having(
                or_(
                    func.coalesce(func.sum(violation_sum.c.violations_count), 0) > 0,
                    func.count(
                        case(
                            (
                                TestAttempt.submission_source
                                == AttemptSubmissionSource.PROCTORING_AUTO.value,
                                TestAttempt.id,
                            ),
                            else_=None,
                        )
                    )
                    > 0,
                    func.avg(attempt_risk) > 0,
                )
            )
        ).all()

        ranked: list[dict] = []
        for row in rows:
            risk_pct = self._round(row.risk_percentage)
            violations = int(row.violations_count or 0)
            reports = int(row.integrity_reports_count or 0)
            composite = risk_pct + violations + reports
            ranked.append(
                {
                    "test_id": int(row.test_id),
                    "test_name": row.test_name,
                    "subject_name": row.subject_name,
                    "risk_percentage": risk_pct,
                    "violations_count": violations,
                    "integrity_reports_count": reports,
                    "average_score": self._round(row.average_score)
                    if row.average_score is not None
                    else None,
                    "_composite": composite,
                }
            )

        ranked.sort(
            key=lambda item: (
                item["_composite"],
                item["risk_percentage"],
                item["violations_count"],
                item["integrity_reports_count"],
            ),
            reverse=True,
        )
        for item in ranked:
            item.pop("_composite", None)
        return ranked[:limit]
