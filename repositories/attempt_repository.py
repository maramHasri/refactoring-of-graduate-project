from datetime import datetime

from sqlalchemy import case, func
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
    def get_by_id(self, attempt_id: int) -> TestAttempt | None:
        return db.session.get(TestAttempt, attempt_id)

    def get_for_test(self, attempt_id: int, test_id: int) -> TestAttempt | None:
        return db.session.execute(
            db.select(TestAttempt).where(
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
                .where(TestAttempt.test_id == test_id)
                .order_by(TestAttempt.started_at.desc())
            ).scalars().all()
        )

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

    def find_graded_for_student_test(
        self,
        *,
        workspace_id: int,
        student_membership_id: int,
        student_user_id: int,
        test_id: int,
    ) -> TestAttempt | None:
        return db.session.execute(
            db.select(TestAttempt)
            .join(Test, Test.id == TestAttempt.test_id)
            .options(joinedload(TestAttempt.test).joinedload(Test.subject))
            .where(
                TestAttempt.test_id == test_id,
                TestAttempt.student_membership_id == student_membership_id,
                TestAttempt.user_id == student_user_id,
                TestAttempt.status == TestAttemptStatus.GRADED.value,
                Test.created_by.has(workspace_id=workspace_id),
            )
            .order_by(TestAttempt.graded_at.desc().nullslast(), TestAttempt.id.desc())
        ).scalars().first()

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
