from models import AIGeneratedQuestion, AIGenerationRequest
from repositories.base_repository import BaseRepository
from utils.db import db


class AIGenerationRequestRepository(BaseRepository):
    def get_by_id(self, request_id: int) -> AIGenerationRequest | None:
        return db.session.get(AIGenerationRequest, request_id)

    def list_questions(self, request_id: int) -> list[AIGeneratedQuestion]:
        return list(
            db.session.execute(
                db.select(AIGeneratedQuestion)
                .where(AIGeneratedQuestion.generation_request_id == request_id)
                .order_by(AIGeneratedQuestion.id)
            ).scalars().all()
        )


class AIGeneratedQuestionRepository(BaseRepository):
    def get_by_id(self, question_id: int) -> AIGeneratedQuestion | None:
        return db.session.get(AIGeneratedQuestion, question_id)

    def list_by_ids_for_request(
        self, request_id: int, question_ids: list[int]
    ) -> list[AIGeneratedQuestion]:
        if not question_ids:
            return []
        return list(
            db.session.execute(
                db.select(AIGeneratedQuestion)
                .where(
                    AIGeneratedQuestion.generation_request_id == request_id,
                    AIGeneratedQuestion.id.in_(question_ids),
                )
                .order_by(AIGeneratedQuestion.id)
            ).scalars().all()
        )
