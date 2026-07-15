"""
Exam blueprint generator — validates instructor blueprints and plans question slots.

Selection and snapshot persistence are orchestrated by TestService.
"""

from __future__ import annotations

from utils.messages import Messages

from dataclasses import dataclass

from models import Question, QuestionBank
from repositories.question_repository import QuestionRepository
from repositories.topic_repository import TopicRepository
from service.exceptions import ValidationError
from service.question_bank_service import QuestionBankService
from utils.exam_blueprint_allocation import distribute_by_percentages

_DIFFICULTY_KEYS = ("easy", "medium", "hard")
_DIFFICULTY_TO_ENUM = {
    "easy": "EASY",
    "medium": "MEDIUM",
    "hard": "HARD",
}


@dataclass(frozen=True)
class QuestionSlot:
    bank_id: int
    topic_id: int
    difficulty: str
    count: int


@dataclass
class BankBlueprintPlan:
    bank_id: int
    requested: int
    slots: list[QuestionSlot]


class ExamBlueprintService:
    def __init__(self):
        self.questions = QuestionRepository()
        self.topics = TopicRepository()
        self.bank_service = QuestionBankService()

    def build_plan(
        self,
        *,
        banks_blueprint: list[dict],
        test_subject_id: int,
        workspace_id: int,
        actor_membership,
    ) -> list[BankBlueprintPlan]:
        resolved_banks = self._resolve_banks(
            banks_blueprint=banks_blueprint,
            test_subject_id=test_subject_id,
            workspace_id=workspace_id,
            actor_membership=actor_membership,
        )
        plans: list[BankBlueprintPlan] = []
        for bank_entry, bank in zip(banks_blueprint, resolved_banks):
            plan = self._plan_for_bank(bank_entry, bank)
            plans.append(plan)
        self._validate_availability(plans)
        return plans

    def select_questions(
        self, plans: list[BankBlueprintPlan]
    ) -> tuple[list[Question], list[dict]]:
        selected: list[Question] = []
        used_question_ids: set[int] = set()
        summary: list[dict] = []

        for plan in plans:
            bank_inserted = 0
            for slot in plan.slots:
                if slot.count <= 0:
                    continue
                batch = self.questions.list_random_by_bank_topic_difficulty(
                    bank_id=slot.bank_id,
                    topic_id=slot.topic_id,
                    difficulty=slot.difficulty,
                    limit=slot.count,
                    exclude_question_ids=used_question_ids,
                )
                if len(batch) < slot.count:
                    topic = self.topics.get_by_id(slot.topic_id)
                    topic_label = topic.name if topic else str(slot.topic_id)
                    raise ValidationError(Messages.NOT_ENOUGH_SLOT_DIFFICULTY_QUESTIONS_INSIDE_TOPIC_TOPIC_LABEL_BANK_SLO.format(slot_difficulty=slot.difficulty, topic_label=topic_label, slot_bank_id=slot.bank_id, slot_count=slot.count, len_batch=len(batch)))
                for question in batch:
                    used_question_ids.add(question.id)
                selected.extend(batch)
                bank_inserted += len(batch)
            summary.append(
                {
                    "bank_id": plan.bank_id,
                    "requested": plan.requested,
                    "inserted": bank_inserted,
                }
            )
        return selected, summary

    def _resolve_banks(
        self,
        *,
        banks_blueprint: list[dict],
        test_subject_id: int,
        workspace_id: int,
        actor_membership,
    ) -> list[QuestionBank]:
        resolved: list[QuestionBank] = []
        for entry in banks_blueprint:
            bank = self.bank_service.resolve_bank_for_exam_blueprint(
                bank_id=entry["bank_id"],
                workspace_id=workspace_id,
                actor_membership=actor_membership,
                test_subject_id=test_subject_id,
            )
            resolved.append(bank)
        return resolved

    def _plan_for_bank(self, bank_entry: dict, bank: QuestionBank) -> BankBlueprintPlan:
        bank_id = bank.id
        question_count = int(bank_entry["question_count"])
        topics = bank_entry["topics"]

        topic_ids = [int(topic["topic_id"]) for topic in topics]
        if len(topic_ids) != len(set(topic_ids)):
            raise ValidationError(Messages.DUPLICATE_TOPIC_ID_ENTRIES_ARE_NOT_ALLOWED_FOR_BANK_BANK_ID.format(bank_id=bank_id))

        topic_weights = {
            str(topic["topic_id"]): int(topic["percentage"]) for topic in topics
        }
        if sum(topic_weights.values()) != 100:
            raise ValidationError(Messages.TOPIC_PERCENTAGES_MUST_TOTAL_100_FOR_BANK_BANK_ID_GOT_SUM_TOPIC.format(bank_id=bank_id, sum_topic_weights_values=sum(topic_weights.values())))

        topic_counts = distribute_by_percentages(question_count, topic_weights)
        slots: list[QuestionSlot] = []

        for topic_entry in topics:
            topic_id = int(topic_entry["topic_id"])
            topic = self.topics.get_by_id(topic_id)
            if not topic:
                raise ValidationError(Messages.TOPIC_TOPIC_ID_DOES_NOT_EXIST.format(topic_id=topic_id))

            if topic.subject_id != bank.subject_id:
                raise ValidationError(Messages.BANK_BANK_ID_DOES_NOT_CONTAIN_TOPIC_TOPIC_ID.format(bank_id=bank_id, topic_id=topic_id))
            if not self.questions.bank_has_topic(bank_id, topic_id):
                topic_label = topic.name
                raise ValidationError(Messages.BANK_BANK_ID_DOES_NOT_CONTAIN_TOPIC_TOPIC_LABEL.format(bank_id=bank_id, topic_label=topic_label))

            dist = topic_entry["difficulty_distribution"]
            diff_weights = {
                "easy": int(dist["easy"]),
                "medium": int(dist["medium"]),
                "hard": int(dist["hard"]),
            }
            diff_sum = sum(diff_weights.values())
            if diff_sum != 100:
                raise ValidationError(Messages.DIFFICULTY_PERCENTAGES_MUST_TOTAL_100_INSIDE_TOPIC_TOPIC_NAME_GOT_DIFF.format(topic_name=topic.name, diff_sum=diff_sum))

            topic_total = topic_counts[str(topic_id)]
            diff_counts = distribute_by_percentages(topic_total, diff_weights)

            for key in _DIFFICULTY_KEYS:
                count = diff_counts[key]
                if count <= 0:
                    continue
                slots.append(
                    QuestionSlot(
                        bank_id=bank_id,
                        topic_id=topic_id,
                        difficulty=_DIFFICULTY_TO_ENUM[key],
                        count=count,
                    )
                )

        return BankBlueprintPlan(
            bank_id=bank_id,
            requested=question_count,
            slots=slots,
        )

    def _validate_availability(self, plans: list[BankBlueprintPlan]) -> None:
        for plan in plans:
            for slot in plan.slots:
                if slot.count <= 0:
                    continue
                available = self.questions.count_active_by_bank_topic_difficulty(
                    bank_id=slot.bank_id,
                    topic_id=slot.topic_id,
                    difficulty=slot.difficulty,
                )
                if available < slot.count:
                    topic = self.topics.get_by_id(slot.topic_id)
                    topic_label = topic.name if topic else str(slot.topic_id)
                    raise ValidationError(Messages.NOT_ENOUGH_SLOT_DIFFICULTY_QUESTIONS_INSIDE_TOPIC_TOPIC_LABEL_REQUESTE.format(slot_difficulty=slot.difficulty, topic_label=topic_label, slot_count=slot.count, available=available))
