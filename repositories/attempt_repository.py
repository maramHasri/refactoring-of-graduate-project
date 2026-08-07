from datetime import datetime

from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import joinedload

from models import (
    AttemptAnswer,
    Subject,
    Test,
    TestAttempt,
    TestQuestion,
    TestStudentAssignment,
    Topic,
)
from models.workspace import Membership
from repositories.base_repository import BaseRepository
from utils.db import db
from utils.enums import QuestionStatus, TestAttemptStatus, TestStatus


class TestAttemptRepository(BaseRepository):
    """Attempt persistence + the canonical Official Attempt selector.

    Official Attempt = latest attempt per (student_membership_id, test_id)
    ordered by ``started_at DESC, id DESC``. Older attempts remain in the DB
    for history/proctoring but must not feed official scores or analytics.
    """

    # --- Official Attempt (canonical) ------------------------------------

    @staticmethod
    def official_attempt_ids_subquery():
        """Subquery of attempt ids that are the official (latest) sitting."""
        rn = (
            func.row_number()
            .over(
                partition_by=(
                    TestAttempt.student_membership_id,
                    TestAttempt.test_id,
                ),
                order_by=(
                    TestAttempt.started_at.desc(),
                    TestAttempt.id.desc(),
                ),
            )
            .label("rn")
        )
        ranked = select(TestAttempt.id.label("attempt_id"), rn).subquery()
        return (
            select(ranked.c.attempt_id.label("attempt_id"))
            .where(ranked.c.rn == 1)
            .subquery()
        )

    @staticmethod
    def official_attempts_subquery():
        """Official attempts with key columns (rn = 1 per student+test)."""
        rn = (
            func.row_number()
            .over(
                partition_by=(
                    TestAttempt.student_membership_id,
                    TestAttempt.test_id,
                ),
                order_by=(
                    TestAttempt.started_at.desc(),
                    TestAttempt.id.desc(),
                ),
            )
            .label("rn")
        )
        ranked = (
            select(
                TestAttempt.id.label("attempt_id"),
                TestAttempt.student_membership_id.label("student_membership_id"),
                TestAttempt.test_id.label("test_id"),
                TestAttempt.status.label("status"),
                TestAttempt.percentage.label("percentage"),
                TestAttempt.final_score.label("final_score"),
                TestAttempt.raw_score.label("raw_score"),
                TestAttempt.graded_at.label("graded_at"),
                TestAttempt.started_at.label("started_at"),
                rn,
            )
        ).subquery()
        return (
            select(
                ranked.c.attempt_id,
                ranked.c.student_membership_id,
                ranked.c.test_id,
                ranked.c.status,
                ranked.c.percentage,
                ranked.c.final_score,
                ranked.c.raw_score,
                ranked.c.graded_at,
                ranked.c.started_at,
            )
            .where(ranked.c.rn == 1)
            .subquery()
        )

    def get_official_attempt(
        self, test_id: int, student_membership_id: int
    ) -> TestAttempt | None:
        """Return the single Official Attempt for a student on a test."""
        return db.session.execute(
            select(TestAttempt)
            .where(
                TestAttempt.test_id == test_id,
                TestAttempt.student_membership_id == student_membership_id,
            )
            .order_by(TestAttempt.started_at.desc(), TestAttempt.id.desc())
            .limit(1)
        ).scalar_one_or_none()

    def count_official_graded_for_test(self, test_id: int) -> int:
        """Students whose Official Attempt on this test is GRADED."""
        official = self.official_attempts_subquery()
        return int(
            db.session.execute(
                select(func.count())
                .select_from(official)
                .where(
                    official.c.test_id == test_id,
                    official.c.status == TestAttemptStatus.GRADED.value,
                )
            ).scalar_one()
            or 0
        )

    def get_by_id(self, attempt_id: int) -> TestAttempt | None:
        return db.session.get(TestAttempt, attempt_id)

    def get_for_test(self, attempt_id: int, test_id: int) -> TestAttempt | None:
        return db.session.execute(
            db.select(TestAttempt)
            .options(joinedload(TestAttempt.user))
            .where(
                TestAttempt.id == attempt_id,
                TestAttempt.test_id == test_id,
            )
        ).scalar_one_or_none()

    def find_active_for_student(
        self, test_id: int, student_membership_id: int
    ) -> TestAttempt | None:
        return db.session.execute(
            db.select(TestAttempt).where(
                TestAttempt.test_id == test_id,
                TestAttempt.student_membership_id == student_membership_id,
                TestAttempt.status == TestAttemptStatus.IN_PROGRESS.value,
            )
        ).scalar_one_or_none()

    def find_completed_for_student(
        self, test_id: int, student_membership_id: int
    ) -> TestAttempt | None:
        return db.session.execute(
            db.select(TestAttempt)
            .where(
                TestAttempt.test_id == test_id,
                TestAttempt.student_membership_id == student_membership_id,
                TestAttempt.status.in_(
                    [
                        TestAttemptStatus.SUBMITTED.value,
                        TestAttemptStatus.GRADED.value,
                    ]
                ),
            )
            .order_by(TestAttempt.submitted_at.desc())
        ).scalar_one_or_none()

    def count_completed_for_student(
        self, test_id: int, student_membership_id: int
    ) -> int:
        return int(
            db.session.execute(
                db.select(db.func.count(TestAttempt.id)).where(
                    TestAttempt.test_id == test_id,
                    TestAttempt.student_membership_id == student_membership_id,
                    TestAttempt.status.in_(
                        [
                            TestAttemptStatus.SUBMITTED.value,
                            TestAttemptStatus.GRADED.value,
                        ]
                    ),
                )
            ).scalar_one()
            or 0
        )

    def list_for_test(self, test_id: int) -> list[TestAttempt]:
        return list(
            db.session.execute(
                db.select(TestAttempt)
                .options(joinedload(TestAttempt.user))
                .where(TestAttempt.test_id == test_id)
                .order_by(TestAttempt.started_at.desc())
            )
            .scalars()
            .unique()
            .all()
        )

    def exam_card_stats_by_test_ids(self, test_ids: list[int]) -> dict[int, dict]:
        """
        Batch exam-card stats per test_id.

        Official-attempt aware:
        - graded_attempts_count / average_score use Official Attempt only
        - participants_count: distinct students with any sitting
        - submitted_attempts_count: Official Attempt status == SUBMITTED
        """
        empty = {
            "participants_count": 0,
            "average_score": None,
            "graded_attempts_count": 0,
            "submitted_attempts_count": 0,
        }
        if not test_ids:
            return {}

        participant_statuses = (
            TestAttemptStatus.IN_PROGRESS.value,
            TestAttemptStatus.SUBMITTED.value,
            TestAttemptStatus.GRADED.value,
        )
        participant_rows = db.session.execute(
            select(
                TestAttempt.test_id,
                func.count(distinct(TestAttempt.student_membership_id)).label(
                    "participants_count"
                ),
            )
            .where(
                TestAttempt.test_id.in_(test_ids),
                TestAttempt.status.in_(participant_statuses),
            )
            .group_by(TestAttempt.test_id)
        ).all()

        official = self.official_attempts_subquery()
        score_expr = case(
            (official.c.final_score.is_not(None), official.c.final_score),
            else_=official.c.raw_score,
        )
        official_rows = db.session.execute(
            select(
                official.c.test_id,
                func.sum(
                    case(
                        (official.c.status == TestAttemptStatus.GRADED.value, 1),
                        else_=0,
                    )
                ).label("graded_attempts_count"),
                func.sum(
                    case(
                        (official.c.status == TestAttemptStatus.SUBMITTED.value, 1),
                        else_=0,
                    )
                ).label("submitted_attempts_count"),
                func.avg(
                    case(
                        (
                            official.c.status == TestAttemptStatus.GRADED.value,
                            score_expr,
                        ),
                        else_=None,
                    )
                ).label("average_score"),
            )
            .where(official.c.test_id.in_(test_ids))
            .group_by(official.c.test_id)
        ).all()

        result: dict[int, dict] = {int(tid): dict(empty) for tid in test_ids}
        for test_id, participants_count in participant_rows:
            result[int(test_id)]["participants_count"] = int(participants_count or 0)
        for (
            test_id,
            graded_attempts_count,
            submitted_attempts_count,
            average_score,
        ) in official_rows:
            avg_value = None
            if average_score is not None:
                avg_value = round(float(average_score), 2)
            entry = result[int(test_id)]
            entry["average_score"] = avg_value
            entry["graded_attempts_count"] = int(graded_attempts_count or 0)
            entry["submitted_attempts_count"] = int(submitted_attempts_count or 0)
        return result

    def exam_card_stats_for_test(self, test_id: int) -> dict:
        return self.exam_card_stats_by_test_ids([test_id]).get(
            int(test_id),
            {
                "participants_count": 0,
                "average_score": None,
                "graded_attempts_count": 0,
                "submitted_attempts_count": 0,
            },
        )

    def average_percentage_by_test_ids(
        self, test_ids: list[int]
    ) -> dict[int, float | None]:
        """Mean percentage of Official GRADED attempts per test."""
        if not test_ids:
            return {}
        official = self.official_attempts_subquery()
        rows = db.session.execute(
            select(
                official.c.test_id,
                func.avg(official.c.percentage),
            )
            .where(
                official.c.test_id.in_(test_ids),
                official.c.status == TestAttemptStatus.GRADED.value,
                official.c.percentage.is_not(None),
            )
            .group_by(official.c.test_id)
        ).all()
        result: dict[int, float | None] = {int(tid): None for tid in test_ids}
        for test_id, avg_value in rows:
            if avg_value is None:
                continue
            result[int(test_id)] = round(float(avg_value), 2)
        return result

    def average_percentage_for_test(self, test_id: int) -> float | None:
        return self.average_percentage_by_test_ids([test_id]).get(int(test_id))

    def map_relevant_attempts_for_monitoring(
        self, test_id: int
    ) -> dict[int, TestAttempt]:
        """One Official Attempt per student for teacher monitoring."""
        official = self.official_attempt_ids_subquery()
        rows = (
            db.session.execute(
                select(TestAttempt)
                .join(official, official.c.attempt_id == TestAttempt.id)
                .options(joinedload(TestAttempt.user))
                .where(TestAttempt.test_id == test_id)
            )
            .scalars()
            .unique()
            .all()
        )
        return {int(a.student_membership_id): a for a in rows}
    def list_published_for_subjects(
        self, subject_ids: list[int], workspace_id: int, student_membership_id: int
    ) -> list[Test]:
        if not subject_ids:
            return []
        return list(
            db.session.execute(
                db.select(Test)
                .join(
                    TestStudentAssignment,
                    TestStudentAssignment.test_id == Test.id,
                )
                .options(
                    joinedload(Test.subject),
                    joinedload(Test.created_by).joinedload(Membership.user),
                )
                .where(
                    Test.subject_id.in_(subject_ids),
                    Test.status == TestStatus.PUBLISHED.value,
                    Test.created_by.has(workspace_id=workspace_id),
                    TestStudentAssignment.student_membership_id == student_membership_id,
                )
                .order_by(Test.published_at.desc().nullslast(), Test.id.desc())
            ).scalars().unique().all()
        )

    def find_test_ids_with_attempt_statuses(
        self,
        test_ids: list[int],
        student_membership_id: int,
        statuses: list[str],
    ) -> set[int]:
        if not test_ids:
            return set()
        rows = db.session.execute(
            db.select(TestAttempt.test_id)
            .where(
                TestAttempt.test_id.in_(test_ids),
                TestAttempt.student_membership_id == student_membership_id,
                TestAttempt.status.in_(statuses),
            )
            .distinct()
        ).scalars().all()
        return set(rows)

    def list_completed_for_student(
        self,
        *,
        workspace_id: int,
        student_membership_id: int,
        student_user_id: int,
    ) -> list[TestAttempt]:
        return list(
            db.session.execute(
                db.select(TestAttempt)
                .join(Test, Test.id == TestAttempt.test_id)
                .options(
                    joinedload(TestAttempt.test).joinedload(Test.subject),
                )
                .where(
                    TestAttempt.student_membership_id == student_membership_id,
                    TestAttempt.user_id == student_user_id,
                    TestAttempt.status.in_(
                        [
                            TestAttemptStatus.SUBMITTED.value,
                            TestAttemptStatus.GRADED.value,
                        ]
                    ),
                    Test.archived_at.is_(None),
                    Test.created_by.has(workspace_id=workspace_id),
                )
                .order_by(
                    TestAttempt.submitted_at.desc().nullslast(),
                    TestAttempt.started_at.desc(),
                    TestAttempt.id.desc(),
                )
            )
            .scalars()
            .unique()
            .all()
        )

    def get_user_last_activity_in_workspace(
        self, user_id: int, workspace_id: int
    ) -> datetime | None:
        return db.session.execute(
            db.select(func.max(TestAttempt.last_activity_at))
            .join(Membership, Membership.id == TestAttempt.student_membership_id)
            .where(
                TestAttempt.user_id == user_id,
                Membership.workspace_id == workspace_id,
            )
        ).scalar_one()

    def list_graded_for_student(
        self,
        *,
        workspace_id: int,
        student_membership_id: int,
        student_user_id: int,
    ) -> list[TestAttempt]:
        """Official Attempts that are GRADED (one per test) for student analytics."""
        official = self.official_attempt_ids_subquery()
        return list(
            db.session.execute(
                select(TestAttempt)
                .join(official, official.c.attempt_id == TestAttempt.id)
                .join(Test, Test.id == TestAttempt.test_id)
                .options(
                    joinedload(TestAttempt.test).joinedload(Test.subject),
                    joinedload(TestAttempt.test)
                    .joinedload(Test.created_by)
                    .joinedload(Membership.user),
                )
                .where(
                    TestAttempt.student_membership_id == student_membership_id,
                    TestAttempt.user_id == student_user_id,
                    TestAttempt.status == TestAttemptStatus.GRADED.value,
                    Test.status == TestStatus.PUBLISHED.value,
                    Test.archived_at.is_(None),
                    Test.created_by.has(workspace_id=workspace_id),
                )
                .order_by(
                    TestAttempt.graded_at.desc().nullslast(),
                    TestAttempt.submitted_at.desc().nullslast(),
                    TestAttempt.id.desc(),
                )
            )
            .scalars()
            .unique()
            .all()
        )

    def list_official_results_for_student(
        self,
        *,
        workspace_id: int,
        student_membership_id: int,
        student_user_id: int,
    ) -> list[TestAttempt]:
        """Official Attempts in SUBMITTED or GRADED for the Results tab.

        IN_PROGRESS official sittings are omitted (no result yet). Older GRADED
        sittings superseded by a newer attempt are excluded automatically.
        """
        official = self.official_attempt_ids_subquery()
        return list(
            db.session.execute(
                select(TestAttempt)
                .join(official, official.c.attempt_id == TestAttempt.id)
                .join(Test, Test.id == TestAttempt.test_id)
                .options(
                    joinedload(TestAttempt.test).joinedload(Test.subject),
                    joinedload(TestAttempt.test)
                    .joinedload(Test.created_by)
                    .joinedload(Membership.user),
                )
                .where(
                    TestAttempt.student_membership_id == student_membership_id,
                    TestAttempt.user_id == student_user_id,
                    TestAttempt.status.in_(
                        [
                            TestAttemptStatus.SUBMITTED.value,
                            TestAttemptStatus.GRADED.value,
                        ]
                    ),
                    Test.status == TestStatus.PUBLISHED.value,
                    Test.archived_at.is_(None),
                    Test.created_by.has(workspace_id=workspace_id),
                )
                .order_by(
                    TestAttempt.submitted_at.desc().nullslast(),
                    TestAttempt.graded_at.desc().nullslast(),
                    TestAttempt.id.desc(),
                )
            )
            .scalars()
            .unique()
            .all()
        )
    def list_recent_for_student(
        self,
        *,
        workspace_id: int,
        student_membership_id: int,
        student_user_id: int,
        offset: int = 0,
        limit: int = 10,
    ) -> tuple[list[TestAttempt], int]:
        """Submitted/graded attempts for the student dashboard Recent Exams table."""
        filters = [
            TestAttempt.student_membership_id == student_membership_id,
            TestAttempt.user_id == student_user_id,
            TestAttempt.status.in_(
                [
                    TestAttemptStatus.SUBMITTED.value,
                    TestAttemptStatus.GRADED.value,
                ]
            ),
            TestAttempt.submitted_at.is_not(None),
            Test.archived_at.is_(None),
            Test.created_by.has(workspace_id=workspace_id),
        ]

        total = (
            db.session.execute(
                db.select(func.count(TestAttempt.id))
                .select_from(TestAttempt)
                .join(Test, Test.id == TestAttempt.test_id)
                .where(*filters)
            ).scalar_one()
            or 0
        )

        rows = list(
            db.session.execute(
                db.select(TestAttempt)
                .join(Test, Test.id == TestAttempt.test_id)
                .options(
                    joinedload(TestAttempt.test).joinedload(Test.subject),
                    joinedload(TestAttempt.test)
                    .joinedload(Test.created_by)
                    .joinedload(Membership.user),
                )
                .where(*filters)
                .order_by(
                    TestAttempt.submitted_at.desc(),
                    TestAttempt.id.desc(),
                )
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .unique()
            .all()
        )
        return rows, int(total)

    def list_all_for_student_workspace(
        self,
        *,
        workspace_id: int,
        student_membership_id: int,
        student_user_id: int,
    ) -> list[TestAttempt]:
        """All attempts for a student in a workspace (any attempt status)."""
        return list(
            db.session.execute(
                db.select(TestAttempt)
                .join(Test, Test.id == TestAttempt.test_id)
                .options(
                    joinedload(TestAttempt.test).joinedload(Test.subject),
                    joinedload(TestAttempt.test)
                    .joinedload(Test.created_by)
                    .joinedload(Membership.user),
                )
                .where(
                    TestAttempt.student_membership_id == student_membership_id,
                    TestAttempt.user_id == student_user_id,
                    Test.archived_at.is_(None),
                    Test.created_by.has(workspace_id=workspace_id),
                )
                .order_by(
                    TestAttempt.started_at.desc(),
                    TestAttempt.id.desc(),
                )
            )
            .scalars()
            .unique()
            .all()
        )

    def find_graded_for_student_test(
        self,
        *,
        workspace_id: int,
        student_membership_id: int,
        student_user_id: int,
        test_id: int,
    ) -> TestAttempt | None:
        """Official Attempt for the test if it is GRADED; else None."""
        attempt = self.get_official_attempt(test_id, student_membership_id)
        if (
            attempt is None
            or attempt.user_id != student_user_id
            or attempt.status != TestAttemptStatus.GRADED.value
        ):
            return None
        # Ensure workspace scope via test creator
        test = db.session.execute(
            select(Test)
            .options(joinedload(Test.subject))
            .where(
                Test.id == test_id,
                Test.created_by.has(workspace_id=workspace_id),
            )
        ).scalar_one_or_none()
        if test is None:
            return None
        attempt.test = test
        return attempt

    def list_topic_weighted_rows_for_subject(
        self,
        *,
        workspace_id: int,
        student_membership_id: int,
        student_user_id: int,
        subject_id: int,
    ) -> list[tuple[int | None, str | None, float, float]]:
        difficulty_weight = case(
            (TestQuestion.snapshot_difficulty == "HARD", 2.0),
            (TestQuestion.snapshot_difficulty == "MEDIUM", 1.5),
            else_=1.0,
        )
        official = self.official_attempt_ids_subquery()
        rows = db.session.execute(
            db.select(
                TestQuestion.snapshot_topic_id.label("topic_id"),
                func.coalesce(
                    TestQuestion.snapshot_topic_name,
                    Topic.name,
                    "General",
                ).label("topic_name"),
                func.sum(
                    func.coalesce(AttemptAnswer.earned_score, 0.0) * difficulty_weight
                ).label("weighted_earned"),
                func.sum(
                    func.coalesce(TestQuestion.points, TestQuestion.snapshot_points, 0.0)
                    * difficulty_weight
                ).label("weighted_possible"),
            )
            .select_from(AttemptAnswer)
            .join(TestAttempt, TestAttempt.id == AttemptAnswer.attempt_id)
            .join(official, official.c.attempt_id == TestAttempt.id)
            .join(Test, Test.id == TestAttempt.test_id)
            .join(TestQuestion, TestQuestion.id == AttemptAnswer.test_question_id)
            .outerjoin(Topic, Topic.id == TestQuestion.snapshot_topic_id)
            .where(
                TestAttempt.student_membership_id == student_membership_id,
                TestAttempt.user_id == student_user_id,
                TestAttempt.status == TestAttemptStatus.GRADED.value,
                Test.subject_id == subject_id,
                Test.created_by.has(workspace_id=workspace_id),
                TestQuestion.status == QuestionStatus.ACTIVE.value,
            )
            .group_by(TestQuestion.snapshot_topic_id, TestQuestion.snapshot_topic_name, Topic.name)
            .order_by(
                func.sum(
                    func.coalesce(AttemptAnswer.earned_score, 0.0) * difficulty_weight
                ).desc()
            )
        ).all()
        return [
            (
                topic_id,
                topic_name,
                float(weighted_earned or 0.0),
                float(weighted_possible or 0.0),
            )
            for topic_id, topic_name, weighted_earned, weighted_possible in rows
        ]

    def list_topic_weighted_rows_for_course(
        self,
        *,
        workspace_id: int,
        student_membership_id: int,
        student_user_id: int,
        course_id: int,
    ) -> list[tuple[int | None, str | None, float, float]]:
        """Backward-compatible alias: course == subject."""
        return self.list_topic_weighted_rows_for_subject(
            workspace_id=workspace_id,
            student_membership_id=student_membership_id,
            student_user_id=student_user_id,
            subject_id=course_id,
        )

    def list_topic_weighted_rows_for_attempt(
        self,
        *,
        attempt_id: int,
    ) -> list[tuple[int | None, str | None, float, float]]:
        difficulty_weight = case(
            (TestQuestion.snapshot_difficulty == "HARD", 2.0),
            (TestQuestion.snapshot_difficulty == "MEDIUM", 1.5),
            else_=1.0,
        )
        rows = db.session.execute(
            db.select(
                TestQuestion.snapshot_topic_id.label("topic_id"),
                func.coalesce(
                    TestQuestion.snapshot_topic_name,
                    Topic.name,
                    "General",
                ).label("topic_name"),
                func.sum(
                    func.coalesce(AttemptAnswer.earned_score, 0.0) * difficulty_weight
                ).label("weighted_earned"),
                func.sum(
                    func.coalesce(TestQuestion.points, TestQuestion.snapshot_points, 0.0)
                    * difficulty_weight
                ).label("weighted_possible"),
            )
            .select_from(AttemptAnswer)
            .join(TestQuestion, TestQuestion.id == AttemptAnswer.test_question_id)
            .outerjoin(Topic, Topic.id == TestQuestion.snapshot_topic_id)
            .where(
                AttemptAnswer.attempt_id == attempt_id,
                TestQuestion.status == QuestionStatus.ACTIVE.value,
            )
            .group_by(TestQuestion.snapshot_topic_id, TestQuestion.snapshot_topic_name, Topic.name)
            .order_by(
                func.sum(
                    func.coalesce(AttemptAnswer.earned_score, 0.0) * difficulty_weight
                ).desc()
            )
        ).all()
        return [
            (
                topic_id,
                topic_name,
                float(weighted_earned or 0.0),
                float(weighted_possible or 0.0),
            )
            for topic_id, topic_name, weighted_earned, weighted_possible in rows
        ]

    def list_topic_weighted_rows_for_attempt_ids(
        self,
        *,
        attempt_ids: list[int],
    ) -> list[tuple[int | None, str | None, int | None, str | None, float, float]]:
        """
        Topic mastery rows across many attempts, including subject context.
        Returns:
          (subject_id, subject_name, topic_id, topic_name, weighted_earned, weighted_possible)
        """
        if not attempt_ids:
            return []

        difficulty_weight = case(
            (TestQuestion.snapshot_difficulty == "HARD", 2.0),
            (TestQuestion.snapshot_difficulty == "MEDIUM", 1.5),
            else_=1.0,
        )
        rows = db.session.execute(
            db.select(
                Test.subject_id.label("subject_id"),
                Subject.name.label("subject_name"),
                TestQuestion.snapshot_topic_id.label("topic_id"),
                func.coalesce(
                    TestQuestion.snapshot_topic_name,
                    Topic.name,
                    "General",
                ).label("topic_name"),
                func.sum(
                    func.coalesce(AttemptAnswer.earned_score, 0.0) * difficulty_weight
                ).label("weighted_earned"),
                func.sum(
                    func.coalesce(TestQuestion.points, TestQuestion.snapshot_points, 0.0)
                    * difficulty_weight
                ).label("weighted_possible"),
            )
            .select_from(AttemptAnswer)
            .join(TestAttempt, TestAttempt.id == AttemptAnswer.attempt_id)
            .join(Test, Test.id == TestAttempt.test_id)
            .outerjoin(Subject, Subject.id == Test.subject_id)
            .join(TestQuestion, TestQuestion.id == AttemptAnswer.test_question_id)
            .outerjoin(Topic, Topic.id == TestQuestion.snapshot_topic_id)
            .where(
                AttemptAnswer.attempt_id.in_(attempt_ids),
                TestQuestion.status == QuestionStatus.ACTIVE.value,
            )
            .group_by(
                Test.subject_id,
                Subject.name,
                TestQuestion.snapshot_topic_id,
                TestQuestion.snapshot_topic_name,
                Topic.name,
            )
        ).all()
        return [
            (
                subject_id,
                subject_name,
                topic_id,
                topic_name,
                float(weighted_earned or 0.0),
                float(weighted_possible or 0.0),
            )
            for (
                subject_id,
                subject_name,
                topic_id,
                topic_name,
                weighted_earned,
                weighted_possible,
            ) in rows
        ]

    def list_topic_weighted_rows_grouped_by_attempt(
        self,
        *,
        attempt_ids: list[int],
    ) -> list[tuple[int, int | None, str | None, float, float]]:
        """
        Per-attempt topic mastery rows (same weighting as get_test_analytics).

        Returns:
          (attempt_id, topic_id, topic_name, weighted_earned, weighted_possible)
        """
        if not attempt_ids:
            return []

        difficulty_weight = case(
            (TestQuestion.snapshot_difficulty == "HARD", 2.0),
            (TestQuestion.snapshot_difficulty == "MEDIUM", 1.5),
            else_=1.0,
        )
        rows = db.session.execute(
            db.select(
                AttemptAnswer.attempt_id.label("attempt_id"),
                TestQuestion.snapshot_topic_id.label("topic_id"),
                func.coalesce(
                    TestQuestion.snapshot_topic_name,
                    Topic.name,
                    "General",
                ).label("topic_name"),
                func.sum(
                    func.coalesce(AttemptAnswer.earned_score, 0.0) * difficulty_weight
                ).label("weighted_earned"),
                func.sum(
                    func.coalesce(TestQuestion.points, TestQuestion.snapshot_points, 0.0)
                    * difficulty_weight
                ).label("weighted_possible"),
            )
            .select_from(AttemptAnswer)
            .join(TestQuestion, TestQuestion.id == AttemptAnswer.test_question_id)
            .outerjoin(Topic, Topic.id == TestQuestion.snapshot_topic_id)
            .where(
                AttemptAnswer.attempt_id.in_(attempt_ids),
                TestQuestion.status == QuestionStatus.ACTIVE.value,
            )
            .group_by(
                AttemptAnswer.attempt_id,
                TestQuestion.snapshot_topic_id,
                TestQuestion.snapshot_topic_name,
                Topic.name,
            )
        ).all()
        return [
            (
                int(attempt_id),
                topic_id,
                topic_name,
                float(weighted_earned or 0.0),
                float(weighted_possible or 0.0),
            )
            for attempt_id, topic_id, topic_name, weighted_earned, weighted_possible in rows
        ]

    def list_in_progress_on_published_tests(self) -> list[TestAttempt]:
        return list(
            db.session.execute(
                db.select(TestAttempt)
                .join(Test, Test.id == TestAttempt.test_id)
                .where(
                    TestAttempt.status == TestAttemptStatus.IN_PROGRESS.value,
                    Test.status == TestStatus.PUBLISHED.value,
                )
            ).scalars().all()
        )

    def list_in_progress_for_timeout(self) -> list[TestAttempt]:
        """IN_PROGRESS attempts that may be due (published or already closed)."""
        return list(
            db.session.execute(
                db.select(TestAttempt)
                .join(Test, Test.id == TestAttempt.test_id)
                .options(joinedload(TestAttempt.test))
                .where(
                    TestAttempt.status == TestAttemptStatus.IN_PROGRESS.value,
                    Test.status.in_(
                        [
                            TestStatus.PUBLISHED.value,
                            TestStatus.CLOSED.value,
                        ]
                    ),
                )
            ).scalars().unique().all()
        )

    def list_in_progress_for_test(self, test_id: int) -> list[TestAttempt]:
        return list(
            db.session.execute(
                db.select(TestAttempt).where(
                    TestAttempt.test_id == test_id,
                    TestAttempt.status == TestAttemptStatus.IN_PROGRESS.value,
                )
            ).scalars().all()
        )

    def list_in_progress_with_global_timing(self) -> list[TestAttempt]:
        """Legacy query — scheduled exams with global timing fields set."""
        return list(
            db.session.execute(
                db.select(TestAttempt)
                .join(Test, Test.id == TestAttempt.test_id)
                .where(
                    TestAttempt.status == TestAttemptStatus.IN_PROGRESS.value,
                    Test.status == TestStatus.PUBLISHED.value,
                    Test.starts_at.is_not(None),
                    Test.duration_minutes.is_not(None),
                )
            ).scalars().all()
        )

    def delete_for_student_in_workspace(
        self, student_membership_id: int, workspace_id: int
    ) -> None:
        rows = db.session.execute(
            db.select(TestAttempt)
            .join(Test, Test.id == TestAttempt.test_id)
            .join(Subject, Subject.id == Test.subject_id)
            .where(
                TestAttempt.student_membership_id == student_membership_id,
                Subject.workspace_id == workspace_id,
            )
        ).scalars().all()
        for row in rows:
            db.session.delete(row)


class AttemptAnswerRepository(BaseRepository):
    def find_by_attempt_and_test_question(
        self, attempt_id: int, test_question_id: int
    ) -> AttemptAnswer | None:
        return db.session.execute(
            db.select(AttemptAnswer).where(
                AttemptAnswer.attempt_id == attempt_id,
                AttemptAnswer.test_question_id == test_question_id,
            )
        ).scalar_one_or_none()

    def list_for_attempt(self, attempt_id: int) -> list[AttemptAnswer]:
        return list(
            db.session.execute(
                db.select(AttemptAnswer)
                .where(AttemptAnswer.attempt_id == attempt_id)
                .order_by(AttemptAnswer.test_question_id)
            ).scalars().all()
        )


class TestQuestionRepositoryExtended(BaseRepository):
    """Additional queries used by attempt runtime (extends test_repository usage)."""

    def get_for_test(self, test_question_id: int, test_id: int) -> TestQuestion | None:
        return db.session.execute(
            db.select(TestQuestion).where(
                TestQuestion.id == test_question_id,
                TestQuestion.test_id == test_id,
            )
        ).scalar_one_or_none()

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

    def count_active_for_test(self, test_id: int) -> int:
        from utils.enums import QuestionStatus

        return int(
            db.session.execute(
                db.select(db.func.count(TestQuestion.id)).where(
                    TestQuestion.test_id == test_id,
                    TestQuestion.status == QuestionStatus.ACTIVE.value,
                )
            ).scalar_one()
            or 0
        )

    def map_ids_for_test(self, test_id: int, test_question_ids: list[int]) -> dict[int, TestQuestion]:
        if not test_question_ids:
            return {}
        rows = list(
            db.session.execute(
                db.select(TestQuestion).where(
                    TestQuestion.test_id == test_id,
                    TestQuestion.id.in_(test_question_ids),
                )
            ).scalars().all()
        )
        return {row.id: row for row in rows}
