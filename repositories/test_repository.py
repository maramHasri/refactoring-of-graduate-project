from models import Test, TestQuestion
from repositories.base_repository import BaseRepository
from utils.db import db


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
