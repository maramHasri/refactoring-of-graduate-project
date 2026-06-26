from models import Question, QuestionChoice, QuestionType
from repositories.base_repository import BaseRepository
from utils.db import db


class QuestionTypeRepository(BaseRepository):
    def find_by_code(self, code: str) -> QuestionType | None:
        normalized = code.strip().upper()
        return db.session.execute(
            db.select(QuestionType).where(
                db.func.upper(QuestionType.code) == normalized
            )
        ).scalar_one_or_none()


class QuestionRepository(BaseRepository):
    def get_by_id(self, question_id: int) -> Question | None:
        return db.session.get(Question, question_id)

    def list_by_bank(self, bank_id: int) -> list[Question]:
        return list(
            db.session.execute(
                db.select(Question)
                .where(
                    Question.bank_id == bank_id,
                    Question.status == "ACTIVE",
                )
                .order_by(Question.id)
            ).scalars().unique().all()
        )

    def get_active_in_bank(self, question_id: int, bank_id: int) -> Question | None:
        return (
            db.session.execute(
                db.select(Question).where(
                    Question.id == question_id,
                    Question.bank_id == bank_id,
                    Question.status == "ACTIVE",
                )
            )
            .scalars()
            .unique()
            .one_or_none()
        )

    def list_random_by_banks(
        self,
        *,
        bank_ids: list[int],
        limit: int,
        difficulty: str | None = None,
        type_code: str | None = None,
        topic_id: int | None = None,
    ) -> list[Question]:
        query = (
            db.select(Question)
            .join(QuestionType, QuestionType.id == Question.question_type_id)
            .where(
                Question.bank_id.in_(bank_ids),
                Question.status == "ACTIVE",
            )
        )
        if difficulty:
            query = query.where(Question.difficulty == difficulty)
        if topic_id:
            query = query.where(Question.topic_id == topic_id)
        if type_code:
            query = query.where(db.func.upper(QuestionType.code) == type_code.upper())

        return list(
            db.session.execute(query.order_by(db.func.random()).limit(limit))
            .scalars()
            .unique()
            .all()
        )

    def count_by_topic_id(self, topic_id: int) -> int:
        return (
            db.session.execute(
                db.select(db.func.count(Question.id)).where(
                    Question.topic_id == topic_id
                )
            ).scalar()
            or 0
        )
