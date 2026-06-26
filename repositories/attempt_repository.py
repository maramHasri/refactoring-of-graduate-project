from models import AttemptAnswer, Test, TestAttempt, TestQuestion
from repositories.base_repository import BaseRepository
from utils.db import db
from utils.enums import TestAttemptStatus, TestStatus


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

    def list_for_test(self, test_id: int) -> list[TestAttempt]:
        return list(
            db.session.execute(
                db.select(TestAttempt)
                .where(TestAttempt.test_id == test_id)
                .order_by(TestAttempt.started_at.desc())
            ).scalars().all()
        )

    def list_published_for_subjects(
        self, subject_ids: list[int], workspace_id: int
    ) -> list[Test]:
        if not subject_ids:
            return []
        return list(
            db.session.execute(
                db.select(Test)
                .where(
                    Test.subject_id.in_(subject_ids),
                    Test.status == TestStatus.PUBLISHED.value,
                    Test.created_by.has(workspace_id=workspace_id),
                )
                .order_by(Test.published_at.desc().nullslast(), Test.id.desc())
            ).scalars().all()
        )


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
