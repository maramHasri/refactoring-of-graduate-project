"""Workspace-scoped queries for the institution admin dashboard."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from models import (
    Membership,
    QuestionBank,
    Subject,
    SubjectMembership,
    Test,
    TestAttempt,
    User,
)
from repositories.base_repository import BaseRepository
from utils.db import db
from utils.enums import (
    MembershipRole,
    MembershipStatus,
    SubjectMembershipStatus,
    SubjectRole,
    TestAttemptStatus,
    TestStatus,
)


class WorkspaceDashboardRepository(BaseRepository):
    def count_active_members_by_role(self, workspace_id: int) -> dict[str, int]:
        rows = db.session.execute(
            select(Membership.role, func.count(Membership.id))
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.workspace_id == workspace_id,
                Membership.status == MembershipStatus.ACTIVE.value,
                User.deleted_at.is_(None),
                Membership.role.in_(
                    [
                        MembershipRole.ADMIN.value,
                        MembershipRole.TEACHER.value,
                        MembershipRole.STUDENT.value,
                    ]
                ),
            )
            .group_by(Membership.role)
        ).all()
        counts = {role: int(count) for role, count in rows}
        return {
            "admins": counts.get(MembershipRole.ADMIN.value, 0),
            "teachers": counts.get(MembershipRole.TEACHER.value, 0),
            "students": counts.get(MembershipRole.STUDENT.value, 0),
        }

    def average_graded_percentage(self, workspace_id: int) -> float:
        value = db.session.execute(
            select(func.avg(TestAttempt.percentage))
            .select_from(TestAttempt)
            .join(Test, Test.id == TestAttempt.test_id)
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .where(
                Membership.workspace_id == workspace_id,
                TestAttempt.status == TestAttemptStatus.GRADED.value,
                TestAttempt.percentage.is_not(None),
                Test.archived_at.is_(None),
            )
        ).scalar()
        if value is None:
            return 0.0
        return round(float(value), 2)

    def most_enrolled_subject(self, workspace_id: int) -> dict | None:
        student_count = func.count(SubjectMembership.id).label("student_count")
        row = db.session.execute(
            select(Subject.id, Subject.name, student_count)
            .join(SubjectMembership, SubjectMembership.subject_id == Subject.id)
            .where(
                Subject.workspace_id == workspace_id,
                Subject.deleted_at.is_(None),
                SubjectMembership.deleted_at.is_(None),
                SubjectMembership.status == SubjectMembershipStatus.ACTIVE.value,
                SubjectMembership.subject_role == SubjectRole.STUDENT.value,
            )
            .group_by(Subject.id, Subject.name)
            .having(student_count > 0)
            .order_by(student_count.desc(), Subject.name.asc(), Subject.id.asc())
            .limit(1)
        ).first()
        if not row:
            return None
        return {
            "subject_id": int(row.id),
            "name": row.name,
            "student_count": int(row.student_count),
        }

    def list_recent_subjects(self, workspace_id: int, *, limit: int = 5) -> list[dict]:
        student_counts = (
            select(
                SubjectMembership.subject_id.label("subject_id"),
                func.count(SubjectMembership.id).label("student_count"),
            )
            .where(
                SubjectMembership.deleted_at.is_(None),
                SubjectMembership.status == SubjectMembershipStatus.ACTIVE.value,
                SubjectMembership.subject_role == SubjectRole.STUDENT.value,
            )
            .group_by(SubjectMembership.subject_id)
            .subquery()
        )
        rows = db.session.execute(
            select(
                Subject,
                func.coalesce(student_counts.c.student_count, 0).label("student_count"),
            )
            .outerjoin(
                student_counts,
                student_counts.c.subject_id == Subject.id,
            )
            .where(
                Subject.workspace_id == workspace_id,
                Subject.deleted_at.is_(None),
            )
            .order_by(Subject.created_at.desc(), Subject.id.desc())
            .limit(limit)
        ).all()
        return [
            {
                "subject": subject,
                "student_count": int(count),
            }
            for subject, count in rows
        ]

    def list_recent_members(self, workspace_id: int, *, limit: int = 5) -> list[tuple]:
        return list(
            db.session.execute(
                select(Membership, User)
                .join(User, User.id == Membership.user_id)
                .where(
                    Membership.workspace_id == workspace_id,
                    Membership.status == MembershipStatus.ACTIVE.value,
                    User.deleted_at.is_(None),
                    Membership.role.in_(
                        [
                            MembershipRole.ADMIN.value,
                            MembershipRole.TEACHER.value,
                            MembershipRole.STUDENT.value,
                        ]
                    ),
                )
                .order_by(
                    Membership.joined_at.desc().nullslast(),
                    Membership.created_at.desc(),
                    Membership.id.desc(),
                )
                .limit(limit)
            ).all()
        )

    def list_recent_question_banks(
        self, workspace_id: int, *, limit: int = 5
    ) -> list[QuestionBank]:
        return list(
            db.session.execute(
                select(QuestionBank)
                .where(
                    QuestionBank.workspace_id == workspace_id,
                    QuestionBank.deleted_at.is_(None),
                )
                .order_by(QuestionBank.updated_at.desc(), QuestionBank.id.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

    def list_upcoming_tests(
        self,
        workspace_id: int,
        *,
        now: datetime,
        limit: int = 10,
    ) -> list[Test]:
        """Institution-admin upcoming: SCHEDULED/PUBLISHED tests not hard-closed."""
        return list(
            db.session.execute(
                select(Test)
                .options(joinedload(Test.subject))
                .join(Membership, Membership.id == Test.created_by_membership_id)
                .where(
                    Membership.workspace_id == workspace_id,
                    Test.status.in_(
                        [TestStatus.SCHEDULED.value, TestStatus.PUBLISHED.value]
                    ),
                    Test.archived_at.is_(None),
                    or_(Test.closed_at.is_(None), Test.closed_at > now),
                    or_(
                        Test.starts_at.is_(None),
                        Test.starts_at >= now,
                        Test.availability_time_mode.in_(["FLEXIBLE", "SURVEY"]),
                        Test.status == TestStatus.SCHEDULED.value,
                    ),
                )
                .order_by(
                    func.coalesce(
                        Test.starts_at,
                        Test.scheduled_publish_at,
                        Test.published_at,
                    )
                    .asc()
                    .nullslast(),
                    Test.id.asc(),
                )
                .limit(limit)
            )
            .scalars()
            .unique()
            .all()
        )

    def graded_performance_trend(
        self,
        workspace_id: int,
        *,
        since: datetime,
    ) -> list[dict]:
        """Daily AVG(percentage) of GRADED attempts since ``since`` (omit empty days)."""
        event_at = func.coalesce(TestAttempt.graded_at, TestAttempt.submitted_at)
        day_bucket = func.date_trunc("day", event_at).label("day")
        rows = db.session.execute(
            select(
                day_bucket,
                func.avg(TestAttempt.percentage).label("average_score"),
                func.count(TestAttempt.id).label("graded_attempts"),
            )
            .select_from(TestAttempt)
            .join(Test, Test.id == TestAttempt.test_id)
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .where(
                Membership.workspace_id == workspace_id,
                TestAttempt.status == TestAttemptStatus.GRADED.value,
                TestAttempt.percentage.is_not(None),
                Test.archived_at.is_(None),
                event_at.is_not(None),
                event_at >= since,
            )
            .group_by(day_bucket)
            .order_by(day_bucket.asc())
        ).all()

        data: list[dict] = []
        for day, average_score, graded_attempts in rows:
            if day is None:
                continue
            if isinstance(average_score, Decimal):
                avg = float(average_score)
            else:
                avg = float(average_score or 0.0)
            day_value = day.date() if hasattr(day, "date") else day
            data.append(
                {
                    "date": day_value.isoformat(),
                    "average_score": round(avg, 2),
                    "graded_attempts": int(graded_attempts or 0),
                }
            )
        return data
