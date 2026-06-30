from datetime import datetime

from sqlalchemy import update

from models import Test, TestQuestion
from repositories.base_repository import BaseRepository
from utils.app_timezone import local_timezone_now
from utils.db import db
from utils.enums import TestStatus


class TestRepository(BaseRepository):
    def get_by_id(self, test_id: int) -> Test | None:
        return db.session.get(Test, test_id)

    def get_by_id_in_workspace(self, test_id: int, workspace_id: int) -> Test | None:
        return db.session.execute(
            db.select(Test).where(
                Test.id == test_id,
                Test.created_by.has(workspace_id=workspace_id),
            )
        ).scalar_one_or_none()

    def list_for_creator(self, creator_membership_id: int) -> list[Test]:
        return list(
            db.session.execute(
                db.select(Test)
                .where(Test.created_by_membership_id == creator_membership_id)
                .order_by(Test.updated_at.desc(), Test.id.desc())
            ).scalars().all()
        )

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


class TestQuestionRepository(BaseRepository):
    def list_for_test(self, test_id: int) -> list[TestQuestion]:
        return list(
            db.session.execute(
                db.select(TestQuestion)
                .where(TestQuestion.test_id == test_id)
                .order_by(TestQuestion.id)
            ).scalars().all()
        )

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
