"""Repository queries for teacher-scoped workspace dashboard."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import joinedload

from models import Membership, Subject, SubjectMembership, Test, TestAttempt
from repositories.base_repository import BaseRepository
from utils.db import db
from utils.enums import (
    SubjectMembershipStatus,
    SubjectRole,
    TestAttemptStatus,
    TestStatus,
)


class TeacherDashboardRepository(BaseRepository):
    def list_active_subjects_by_ids(self, subject_ids: list[int]) -> list[Subject]:
        if not subject_ids:
            return []
        return list(
            db.session.execute(
                select(Subject)
                .where(
                    Subject.id.in_(subject_ids),
                    Subject.deleted_at.is_(None),
                )
                .order_by(Subject.name, Subject.id)
            )
            .scalars()
            .all()
        )

    def list_active_subject_ids_for_workspace(self, workspace_id: int) -> list[int]:
        return list(
            db.session.execute(
                select(Subject.id)
                .where(
                    Subject.workspace_id == workspace_id,
                    Subject.deleted_at.is_(None),
                )
                .order_by(Subject.id)
            )
            .scalars()
            .all()
        )

    def count_distinct_students_for_subjects(self, subject_ids: list[int]) -> int:
        if not subject_ids:
            return 0
        return int(
            db.session.execute(
                select(func.count(distinct(SubjectMembership.membership_id)))
                .where(
                    SubjectMembership.subject_id.in_(subject_ids),
                    SubjectMembership.subject_role == SubjectRole.STUDENT.value,
                    SubjectMembership.status == SubjectMembershipStatus.ACTIVE.value,
                    SubjectMembership.deleted_at.is_(None),
                )
            ).scalar_one()
            or 0
        )

    def count_students_per_subject(self, subject_ids: list[int]) -> dict[int, int]:
        if not subject_ids:
            return {}
        rows = db.session.execute(
            select(
                SubjectMembership.subject_id,
                func.count(SubjectMembership.id),
            )
            .where(
                SubjectMembership.subject_id.in_(subject_ids),
                SubjectMembership.subject_role == SubjectRole.STUDENT.value,
                SubjectMembership.status == SubjectMembershipStatus.ACTIVE.value,
                SubjectMembership.deleted_at.is_(None),
            )
            .group_by(SubjectMembership.subject_id)
        ).all()
        return {int(subject_id): int(count) for subject_id, count in rows}

    def list_graded_attempts_for_subjects(
        self,
        *,
        workspace_id: int,
        subject_ids: list[int],
    ) -> list[TestAttempt]:
        """GRADED attempts on PUBLISHED, non-archived tests in the teacher's subjects."""
        if not subject_ids:
            return []
        return list(
            db.session.execute(
                select(TestAttempt)
                .join(Test, Test.id == TestAttempt.test_id)
                .join(Membership, Membership.id == Test.created_by_membership_id)
                .options(
                    joinedload(TestAttempt.test).joinedload(Test.subject),
                )
                .where(
                    Membership.workspace_id == workspace_id,
                    Test.subject_id.in_(subject_ids),
                    TestAttempt.status == TestAttemptStatus.GRADED.value,
                    TestAttempt.percentage.is_not(None),
                    Test.status == TestStatus.PUBLISHED.value,
                    Test.archived_at.is_(None),
                )
                .order_by(
                    TestAttempt.graded_at.desc().nullslast(),
                    TestAttempt.id.desc(),
                )
            )
            .scalars()
            .unique()
            .all()
        )

    def count_graded_tests_per_subject(
        self,
        *,
        workspace_id: int,
        subject_ids: list[int],
    ) -> dict[int, int]:
        """Distinct tests with ≥1 GRADED attempt, per subject."""
        if not subject_ids:
            return {}
        rows = db.session.execute(
            select(Test.subject_id, func.count(distinct(Test.id)))
            .select_from(TestAttempt)
            .join(Test, Test.id == TestAttempt.test_id)
            .join(Membership, Membership.id == Test.created_by_membership_id)
            .where(
                Membership.workspace_id == workspace_id,
                Test.subject_id.in_(subject_ids),
                TestAttempt.status == TestAttemptStatus.GRADED.value,
                Test.status == TestStatus.PUBLISHED.value,
                Test.archived_at.is_(None),
            )
            .group_by(Test.subject_id)
        ).all()
        return {int(subject_id): int(count) for subject_id, count in rows}

    def list_upcoming_tests_for_subjects(
        self,
        *,
        workspace_id: int,
        subject_ids: list[int],
        now: datetime,
        limit: int = 5,
    ) -> list[Test]:
        if not subject_ids:
            return []
        return list(
            db.session.execute(
                select(Test)
                .options(joinedload(Test.subject))
                .join(Membership, Membership.id == Test.created_by_membership_id)
                .where(
                    Membership.workspace_id == workspace_id,
                    Test.subject_id.in_(subject_ids),
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

    def list_recent_created_tests(
        self,
        *,
        creator_membership_id: int,
        limit: int = 5,
    ) -> list[Test]:
        return list(
            db.session.execute(
                select(Test)
                .options(joinedload(Test.subject))
                .where(Test.created_by_membership_id == creator_membership_id)
                .order_by(Test.created_at.desc(), Test.id.desc())
                .limit(limit)
            )
            .scalars()
            .unique()
            .all()
        )
