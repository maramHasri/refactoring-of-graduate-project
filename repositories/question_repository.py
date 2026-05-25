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
