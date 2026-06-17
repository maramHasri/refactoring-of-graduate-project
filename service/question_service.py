"""
Create questions inside question banks (single endpoint, multiple type_code values).
"""
from decimal import Decimal

from models import Question, QuestionBank, QuestionChoice
from repositories.question_repository import QuestionRepository, QuestionTypeRepository
from repositories.topic_repository import TopicRepository
from service.exceptions import NotFoundError, ValidationError
from service.question_bank_service import QuestionBankService
from utils.db import db
from utils.enums import Difficulty, QuestionStatus
from utils.question_type_validation import validate_question_create_payload


class QuestionService:
    def __init__(self):
        self.questions = QuestionRepository()
        self.question_types = QuestionTypeRepository()
        self.topics = TopicRepository()
        self.bank_service = QuestionBankService()

    def create_questions_in_bank(
        self,
        *,
        bank_id: int,
        workspace_id: int,
        owner_user_id: int,
        actor_membership,
        questions: list[dict],
    ) -> list[Question]:
        """
        POST /question-banks/{bankId}/questions — transactional create for all items.
        Rolls back entirely if any question fails validation or persistence.
        """
        bank = self.bank_service.resolve_bank_for_question_write(
            bank_id=bank_id,
            workspace_id=workspace_id,
            actor_membership=actor_membership,
        )

        if not questions:
            raise ValidationError("questions must contain at least one item")

        created: list[Question] = []
        try:
            for index, payload in enumerate(questions):
                created.append(
                    self._persist_question_in_bank(
                        bank=bank,
                        workspace_id=workspace_id,
                        owner_user_id=owner_user_id,
                        payload=payload,
                        item_index=index,
                    )
                )
            db.session.commit()
            for question in created:
                db.session.refresh(question)
            return created
        except Exception:
            db.session.rollback()
            raise

    def _persist_question_in_bank(
        self,
        *,
        bank: QuestionBank,
        workspace_id: int,
        owner_user_id: int,
        payload: dict,
        item_index: int,
    ) -> Question:
        """Validate and stage one question + choices (no commit)."""
        prefix = f"questions[{item_index}]"

        type_code = validate_question_create_payload(
            type_code=payload["type_code"],
            choices=payload.get("choices"),
        )
        question_type = self.question_types.find_by_code(type_code)
        if not question_type:
            raise ValidationError(
                f"{prefix}: question type '{type_code}' is not configured. Run flask seed."
            )

        topic_id = self._resolve_optional_topic_id(
            payload.get("topic_id"),
            subject_id=bank.subject_id,
            workspace_id=workspace_id,
            field_prefix=prefix,
        )

        difficulty = payload.get("difficulty")
        if difficulty is not None:
            difficulty = difficulty.strip().upper()
            if difficulty not in [d.value for d in Difficulty]:
                raise ValidationError(f"{prefix}: invalid difficulty value")

        points = payload.get("points")
        if points is not None:
            points = Decimal(str(points))
            if points < 0:
                raise ValidationError(f"{prefix}: points must be non-negative")

        question = Question(
            bank_id=bank.id,
            question_text=payload["body"].strip(),
            explanation=(payload.get("explanation") or "").strip() or None,
            question_type_id=question_type.id,
            owner_user_id=owner_user_id,
            status=QuestionStatus.ACTIVE.value,
            topic_id=topic_id,
            points=points,
            difficulty=difficulty,
        )
        self.questions.add(question)
        db.session.flush()

        for choice_index, choice_data in enumerate(payload.get("choices") or []):
            choice = QuestionChoice(
                question_id=question.id,
                body=choice_data["body"].strip(),
                is_correct=bool(choice_data["is_correct"]),
                order_index=choice_data.get("order_index", choice_index),
            )
            self.questions.add(choice)

        return question

    def list_questions_in_bank(
        self, *, bank_id: int, workspace_id: int, actor_membership
    ) -> list[dict]:
        bank = self.bank_service.resolve_bank_for_question_view(
            bank_id=bank_id,
            workspace_id=workspace_id,
            actor_membership=actor_membership,
        )
        rows = self.questions.list_by_bank(bank.id)
        return [self.serialize_question(q) for q in rows]

    def update_question_in_bank(
        self,
        *,
        bank_id: int,
        question_id: int,
        workspace_id: int,
        actor_membership,
        data: dict,
    ) -> Question:
        bank = self.bank_service.resolve_bank_for_question_write(
            bank_id=bank_id,
            workspace_id=workspace_id,
            actor_membership=actor_membership,
        )
        question = self.questions.get_active_in_bank(question_id, bank.id)
        if not question:
            raise NotFoundError("Question not found in this bank")

        if "type_code" in data or "choices" in data:
            type_code = (
                validate_question_create_payload(
                    type_code=data.get("type_code")
                    or (
                        question.question_type.code.upper()
                        if question.question_type and question.question_type.code
                        else ""
                    ),
                    choices=data.get("choices")
                    if "choices" in data
                    else [
                        {
                            "body": choice.body,
                            "is_correct": choice.is_correct,
                            "order_index": choice.order_index,
                        }
                        for choice in question.choices
                    ],
                )
            )
            if "type_code" in data:
                question_type = self.question_types.find_by_code(type_code)
                if not question_type:
                    raise ValidationError(
                        f"Question type '{type_code}' is not configured. Run flask seed."
                    )
                question.question_type_id = question_type.id

        if "body" in data and data["body"]:
            question.question_text = data["body"].strip()
        if "explanation" in data:
            question.explanation = (data.get("explanation") or "").strip() or None
        if "topic_id" in data:
            question.topic_id = self._resolve_optional_topic_id(
                data.get("topic_id"),
                subject_id=bank.subject_id,
                workspace_id=workspace_id,
            )
        if "difficulty" in data:
            difficulty = data.get("difficulty")
            if difficulty is None:
                question.difficulty = None
            else:
                difficulty = difficulty.strip().upper()
                if difficulty not in [d.value for d in Difficulty]:
                    raise ValidationError("invalid difficulty value")
                question.difficulty = difficulty
        if "points" in data:
            points = data.get("points")
            if points is None:
                question.points = None
            else:
                points = Decimal(str(points))
                if points < 0:
                    raise ValidationError("points must be non-negative")
                question.points = points

        if "choices" in data:
            for choice in list(question.choices):
                db.session.delete(choice)
            db.session.flush()
            for choice_index, choice_data in enumerate(data.get("choices") or []):
                choice = QuestionChoice(
                    question_id=question.id,
                    body=choice_data["body"].strip(),
                    is_correct=bool(choice_data["is_correct"]),
                    order_index=choice_data.get("order_index", choice_index),
                )
                self.questions.add(choice)

        db.session.commit()
        db.session.refresh(question)
        return question

    def delete_question_in_bank(
        self,
        *,
        bank_id: int,
        question_id: int,
        workspace_id: int,
        actor_membership,
    ) -> Question:
        bank = self.bank_service.resolve_bank_for_question_write(
            bank_id=bank_id,
            workspace_id=workspace_id,
            actor_membership=actor_membership,
        )
        question = self.questions.get_active_in_bank(question_id, bank.id)
        if not question:
            raise NotFoundError("Question not found in this bank")

        question.status = QuestionStatus.ARCHIVED.value
        db.session.commit()
        return question

    def _resolve_optional_topic_id(
        self,
        topic_id,
        *,
        subject_id: int,
        workspace_id: int,
        field_prefix: str = "question",
    ) -> int | None:
        if topic_id is None:
            return None
        try:
            topic_id = int(topic_id)
        except (TypeError, ValueError):
            raise ValidationError(f"{field_prefix}: topic_id must be a valid integer")
        if topic_id <= 0:
            return None

        topic = self.topics.get_in_subject(
            topic_id, subject_id=subject_id, workspace_id=workspace_id
        )
        if not topic:
            raise ValidationError(
                f"{field_prefix}: topic_id must reference an existing topic "
                "in the bank's subject"
            )
        return topic.id

    def serialize_question(self, question: Question) -> dict:
        return {
            "id": question.id,
            "bank_id": question.bank_id,
            "type_code": (
                question.question_type.code.upper()
                if question.question_type and question.question_type.code
                else None
            ),
            "body": question.question_text,
            "explanation": question.explanation,
            "points": float(question.points) if question.points is not None else None,
            "difficulty": question.difficulty,
            "topic_id": question.topic_id,
            "status": question.status,
            "owner_user_id": question.owner_user_id,
            "choices": [
                {
                    "id": c.id,
                    "body": c.body,
                    "is_correct": c.is_correct,
                    "order_index": c.order_index,
                }
                for c in sorted(
                    question.choices,
                    key=lambda row: (row.order_index is None, row.order_index or 0),
                )
            ],
            "created_at": question.created_at.isoformat() if question.created_at else None,
            "updated_at": question.updated_at.isoformat() if question.updated_at else None,
        }
