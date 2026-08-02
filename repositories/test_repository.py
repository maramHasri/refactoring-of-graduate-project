from datetime import datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import joinedload

from models import Test, TestQuestion, TestStudentAssignment
from models.workspace import Membership
from repositories.base_repository import BaseRepository
from utils.app_timezone import ensure_local_aware, local_timezone_now
from utils.db import db
from utils.enums import AvailabilityTimeMode, TestStatus


class TestRepository(BaseRepository):
    def get_by_id(self, test_id: int) -> Test | None:
        return db.session.get(Test, test_id)

    def get_by_id_in_workspace(self, test_id: int, workspace_id: int) -> Test | None:
        return db.session.execute(
            db.select(Test)
            .options(
                joinedload(Test.subject),
                joinedload(Test.created_by).joinedload(Membership.user),
            )
            .where(
                Test.id == test_id,
                Test.created_by.has(workspace_id=workspace_id),
            )
        ).unique().scalar_one_or_none()

    def count_for_creator(self, creator_membership_id: int) -> int:
        return (
            db.session.execute(
                db.select(db.func.count(Test.id)).where(
                    Test.created_by_membership_id == creator_membership_id
                )
            ).scalar_one()
            or 0
        )

    def count_by_subject_ids(self, subject_ids: list[int]) -> dict[int, int]:
        """Non-archived tests per subject."""
        if not subject_ids:
            return {}
        rows = db.session.execute(
            db.select(Test.subject_id, db.func.count(Test.id))
            .where(
                Test.subject_id.in_(subject_ids),
                Test.archived_at.is_(None),
            )
            .group_by(Test.subject_id)
        ).all()
        result = {int(sid): 0 for sid in subject_ids}
        for subject_id, count in rows:
            if subject_id is not None:
                result[int(subject_id)] = int(count)
        return result

    def list_for_creator(self, creator_membership_id: int) -> list[Test]:
        rows, _total = self.list_for_creator_paginated(
            creator_membership_id,
            include_archived=True,
            offset=0,
            limit=10_000,
        )
        return rows

    def list_for_creator_paginated(
        self,
        creator_membership_id: int,
        *,
        include_archived: bool = False,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Test], int]:
        filters = [Test.created_by_membership_id == creator_membership_id]
        if not include_archived:
            filters.append(Test.status != TestStatus.ARCHIVED.value)

        total = (
            db.session.execute(
                db.select(db.func.count(Test.id)).where(*filters)
            ).scalar_one()
            or 0
        )
        rows = list(
            db.session.execute(
                db.select(Test)
                .where(*filters)
                .order_by(Test.updated_at.desc(), Test.id.desc())
                .offset(offset)
                .limit(limit)
            ).scalars().all()
        )
        return rows, int(total)

    def count_created_by_membership_ids(
        self, membership_ids: list[int]
    ) -> dict[int, int]:
        """Count non-archived tests created by each membership id."""
        if not membership_ids:
            return {}
        rows = db.session.execute(
            db.select(
                Test.created_by_membership_id,
                db.func.count(Test.id),
            )
            .where(
                Test.created_by_membership_id.in_(membership_ids),
                Test.archived_at.is_(None),
            )
            .group_by(Test.created_by_membership_id)
        ).all()
        return {
            int(membership_id): int(count)
            for membership_id, count in rows
            if membership_id is not None
        }

    def list_for_workspace(
        self,
        workspace_id: int,
        *,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Test], int]:
        """All tests created by members of this workspace (any creator)."""
        filters = [Test.created_by.has(workspace_id=workspace_id)]
        if status:
            filters.append(Test.status == status)

        total = (
            db.session.execute(
                db.select(db.func.count(Test.id)).where(*filters)
            ).scalar_one()
            or 0
        )
        rows = list(
            db.session.execute(
                db.select(Test)
                .options(
                    joinedload(Test.subject),
                    joinedload(Test.created_by).joinedload(Membership.user),
                )
                .where(*filters)
                .order_by(Test.updated_at.desc(), Test.id.desc())
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .unique()
            .all()
        )
        return rows, int(total)

    def find_by_slug(self, slug: str) -> Test | None:
        return db.session.execute(
            db.select(Test).where(Test.slug == slug)
        ).scalar_one_or_none()

    def delete(self, test: Test) -> None:
        db.session.delete(test)

    def publish_due_scheduled_tests(self, *, now: datetime | None = None) -> list[int]:
        """Atomically publish SCHEDULED tests whose scheduled_publish_at has passed."""
        now = now or local_timezone_now()
        stmt = (
            update(Test)
            .where(
                Test.status == TestStatus.SCHEDULED.value,
                Test.scheduled_publish_at.is_not(None),
                Test.scheduled_publish_at <= now,
            )
            .values(
                status=TestStatus.PUBLISHED.value,
                published_at=now,
                scheduled_publish_at=None,
            )
            .returning(Test.id)
        )
        result = db.session.execute(stmt)
        published_ids = [row[0] for row in result.all()]
        if published_ids:
            db.session.commit()
        return published_ids

    def list_published_scheduled_for_auto_close(self) -> list[Test]:
        """
        PUBLISHED non-flexible/non-survey tests that have starts_at + duration configured.

        Callers decide which rows are due using the shared scheduled global-end helper.
        """
        return list(
            db.session.execute(
                db.select(Test)
                .where(
                    Test.status == TestStatus.PUBLISHED.value,
                    Test.archived_at.is_(None),
                    Test.starts_at.is_not(None),
                    Test.duration_minutes.is_not(None),
                    or_(
                        Test.availability_time_mode.is_(None),
                        Test.availability_time_mode
                        == AvailabilityTimeMode.SCHEDULED.value,
                    ),
                )
                .order_by(Test.id.asc())
            )
            .scalars()
            .all()
        )

    def list_published_flexible_due_for_auto_close(
        self, *, now: datetime | None = None
    ) -> list[Test]:
        """
        PUBLISHED flexible tests whose planned closed_at has been reached.

        closed_at is availability end only; callers must use _apply_test_close
        (do not finalize in-progress attempts here).
        """
        now = now or local_timezone_now()
        return list(
            db.session.execute(
                db.select(Test)
                .where(
                    Test.status == TestStatus.PUBLISHED.value,
                    Test.archived_at.is_(None),
                    Test.availability_time_mode == AvailabilityTimeMode.FLEXIBLE.value,
                    Test.closed_at.is_not(None),
                    Test.closed_at <= now,
                )
                .order_by(Test.id.asc())
            )
            .scalars()
            .all()
        )

    def _find_time_overlapping_scheduled_test_ids(
        self,
        *,
        workspace_id: int,
        window_start: datetime,
        window_end: datetime,
        exclude_test_id: int | None = None,
        teacher_membership_id: int | None = None,
    ) -> list[int]:
        stmt = (
            select(Test.id, Test.starts_at, Test.duration_minutes)
            .where(
                Test.created_by.has(workspace_id=workspace_id),
                Test.status.in_(
                    [TestStatus.SCHEDULED.value, TestStatus.PUBLISHED.value]
                ),
                Test.archived_at.is_(None),
                Test.starts_at.is_not(None),
                Test.duration_minutes.is_not(None),
                Test.starts_at < window_end,
                or_(
                    Test.availability_time_mode.is_(None),
                    Test.availability_time_mode.notin_(
                        [
                            AvailabilityTimeMode.FLEXIBLE.value,
                            AvailabilityTimeMode.SURVEY.value,
                        ]
                    ),
                ),
            )
        )
        if exclude_test_id is not None:
            stmt = stmt.where(Test.id != exclude_test_id)
        if teacher_membership_id is not None:
            stmt = stmt.where(Test.created_by_membership_id == teacher_membership_id)

        candidate_rows = db.session.execute(stmt).all()
        overlapping_ids: list[int] = []
        for test_id, starts_at, duration_minutes in candidate_rows:
            if not starts_at or not duration_minutes:
                continue
            start = ensure_local_aware(starts_at)
            end = start + timedelta(minutes=int(duration_minutes))
            if start < window_end and end > window_start:
                overlapping_ids.append(int(test_id))
        return sorted(overlapping_ids)

    def find_conflicting_teacher_scheduled_test_id(
        self,
        *,
        workspace_id: int,
        teacher_membership_id: int,
        window_start: datetime,
        window_end: datetime,
        exclude_test_id: int | None = None,
    ) -> int | None:
        overlapping_ids = self._find_time_overlapping_scheduled_test_ids(
            workspace_id=workspace_id,
            window_start=window_start,
            window_end=window_end,
            exclude_test_id=exclude_test_id,
            teacher_membership_id=teacher_membership_id,
        )
        return overlapping_ids[0] if overlapping_ids else None

    def find_conflicting_scheduled_test_ids(
        self,
        *,
        workspace_id: int,
        window_start: datetime,
        window_end: datetime,
        student_membership_ids: list[int],
        exclude_test_id: int | None = None,
    ) -> list[int]:
        """
        Return test IDs that overlap [window_start, window_end) and share
        at least one assigned student with student_membership_ids.
        """
        if not student_membership_ids:
            return []

        overlapping_ids = self._find_time_overlapping_scheduled_test_ids(
            workspace_id=workspace_id,
            window_start=window_start,
            window_end=window_end,
            exclude_test_id=exclude_test_id,
        )
        if not overlapping_ids:
            return []

        return list(
            db.session.execute(
                select(TestStudentAssignment.test_id)
                .where(
                    TestStudentAssignment.test_id.in_(overlapping_ids),
                    TestStudentAssignment.student_membership_id.in_(
                        student_membership_ids
                    ),
                )
                .distinct()
                .order_by(TestStudentAssignment.test_id)
            )
            .scalars()
            .all()
        )


class TestQuestionRepository(BaseRepository):
    def list_for_test(self, test_id: int) -> list[TestQuestion]:
        return list(
            db.session.execute(
                db.select(TestQuestion)
                .where(TestQuestion.test_id == test_id)
                .order_by(TestQuestion.id)
            ).scalars().all()
        )

    def list_active_for_test(self, test_id: int) -> list[TestQuestion]:
        from utils.enums import QuestionStatus

        return list(
            db.session.execute(
                db.select(TestQuestion)
                .where(
                    TestQuestion.test_id == test_id,
                    TestQuestion.status == QuestionStatus.ACTIVE.value,
                )
                .order_by(TestQuestion.id)
            ).scalars().all()
        )

    def count_by_test_ids(self, test_ids: list[int]) -> dict[int, int]:
        """Batch count of TestQuestion rows per test (all statuses)."""
        if not test_ids:
            return {}
        rows = db.session.execute(
            db.select(TestQuestion.test_id, db.func.count(TestQuestion.id))
            .where(TestQuestion.test_id.in_(test_ids))
            .group_by(TestQuestion.test_id)
        ).all()
        result = {int(test_id): 0 for test_id in test_ids}
        for test_id, count in rows:
            result[int(test_id)] = int(count or 0)
        return result

    def count_for_test(self, test_id: int) -> int:
        return self.count_by_test_ids([test_id]).get(int(test_id), 0)

    def find_by_test_and_question(self, test_id: int, question_id: int) -> TestQuestion | None:
        return db.session.execute(
            db.select(TestQuestion).where(
                TestQuestion.test_id == test_id,
                TestQuestion.question_id == question_id,
            )
        ).scalar_one_or_none()

    def get_for_test(self, test_question_id: int, test_id: int) -> TestQuestion | None:
        return db.session.execute(
            db.select(TestQuestion).where(
                TestQuestion.id == test_question_id,
                TestQuestion.test_id == test_id,
            )
        ).scalar_one_or_none()

    def delete(self, row: TestQuestion) -> None:
        db.session.delete(row)
