"""
Deterministic, state-driven exam grading workflow.

Question type is consulted only during initial auto-grading on submit.
After submission the workflow relies on AnswerGradingStatus and TestAttemptStatus.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

from models import AttemptAnswer, Test, TestAttempt, TestQuestion
from repositories.attempt_grading_audit_repository import AttemptGradingAuditRepository
from repositories.attempt_repository import (
    AttemptAnswerRepository,
    TestQuestionRepositoryExtended,
)
from service.email_delivery_service import EmailDeliveryError, EmailDeliveryService
from service.exceptions import ValidationError
from utils.enums import (
    AnswerGradingStatus,
    AttemptGradingAuditAction,
    TestAttemptStatus,
)

logger = logging.getLogger(__name__)

_OBJECTIVE_TYPES = frozenset({"MCQ", "TRUE_FALSE", "MULTI_SELECT"})


class ExamGradingService:
    def __init__(self):
        self.answers = AttemptAnswerRepository()
        self.test_questions = TestQuestionRepositoryExtended()
        self.audit = AttemptGradingAuditRepository()
        self.email = EmailDeliveryService()

    def process_submission_grading(
        self,
        attempt: TestAttempt,
        test: Test,
        *,
        submission_source: str,
        actor_membership_id: int | None = None,
        actor_user_id: int | None = None,
    ) -> bool:
        """
        Run auto-grading and finalize attempt status after submit.
        Returns True when the attempt becomes GRADED for the first time.
        """
        self._log_audit(
            attempt.id,
            AttemptGradingAuditAction.ATTEMPT_SUBMITTED.value,
            actor_membership_id=actor_membership_id,
            actor_user_id=actor_user_id,
            details={"submission_source": submission_source},
        )
        self._run_initial_auto_grading(attempt, test)
        self._log_audit(
            attempt.id,
            AttemptGradingAuditAction.AUTO_GRADING_COMPLETED.value,
            actor_membership_id=actor_membership_id,
            actor_user_id=actor_user_id,
        )
        return self.finalize_if_complete(
            attempt,
            test,
            actor_membership_id=actor_membership_id,
            actor_user_id=actor_user_id,
        )

    def grade_pending_answers(
        self,
        attempt: TestAttempt,
        test: Test,
        grades: list[dict],
        *,
        actor_membership_id: int,
        actor_user_id: int | None = None,
    ) -> tuple[str, bool]:
        """
        Manually grade answers in PENDING_REVIEW state only.
        Returns (message, became_graded_first_time).
        """
        if not grades:
            raise ValidationError("At least one answer grade is required")

        pending_by_question = self._pending_answers_by_question(attempt)
        if not pending_by_question:
            raise ValidationError("No answers are pending manual grading")

        self._log_audit(
            attempt.id,
            AttemptGradingAuditAction.MANUAL_GRADING_STARTED.value,
            actor_membership_id=actor_membership_id,
            actor_user_id=actor_user_id,
            details={"answer_count": len(grades)},
        )

        question_rows = {
            row.id: row
            for row in self.test_questions.list_active_for_test(test.id)
        }

        graded_ids: list[int] = []
        for item in grades:
            test_question_id = int(item["test_question_id"])
            answer = pending_by_question.get(test_question_id)
            if not answer:
                raise ValidationError(
                    f"test_question_id {test_question_id} is not pending manual grading"
                )

            test_question = question_rows.get(test_question_id)
            if not test_question:
                raise ValidationError(
                    f"test_question_id {test_question_id} is not part of this exam"
                )

            max_points = Decimal(str(test_question.points or 0))
            earned = Decimal(str(item["earned_score"]))
            if earned > max_points:
                raise ValidationError(
                    f"earned_score for question {test_question_id} cannot exceed "
                    f"{max_points}"
                )

            answer.earned_score = earned
            answer.is_correct = None
            answer.grading_status = AnswerGradingStatus.MANUALLY_GRADED.value
            if "teacher_feedback" in item:
                feedback = item.get("teacher_feedback")
                answer.teacher_feedback = (feedback or "").strip() or None
            graded_ids.append(test_question_id)

        self._log_audit(
            attempt.id,
            AttemptGradingAuditAction.MANUAL_GRADING_COMPLETED.value,
            actor_membership_id=actor_membership_id,
            actor_user_id=actor_user_id,
            details={"test_question_ids": graded_ids},
        )

        became_graded = self.finalize_if_complete(
            attempt,
            test,
            actor_membership_id=actor_membership_id,
            actor_user_id=actor_user_id,
        )
        if self.has_pending_review(attempt):
            message = "Manual grades saved; attempt is still waiting for grading"
        elif became_graded:
            message = "Attempt fully graded"
        else:
            message = "Manual grades saved"
        return message, became_graded

    def finalize_if_complete(
        self,
        attempt: TestAttempt,
        test: Test,
        *,
        actor_membership_id: int | None = None,
        actor_user_id: int | None = None,
    ) -> bool:
        """Finalize attempt to GRADED when no answers are pending review."""
        if self.has_pending_review(attempt):
            attempt.status = TestAttemptStatus.SUBMITTED.value
            return False

        first_time = attempt.graded_at is None
        attempt.status = TestAttemptStatus.GRADED.value
        self.recompute_attempt_scores(attempt, test)
        if first_time:
            attempt.graded_at = datetime.now(timezone.utc)
            self._log_audit(
                attempt.id,
                AttemptGradingAuditAction.ATTEMPT_FULLY_GRADED.value,
                actor_membership_id=actor_membership_id,
                actor_user_id=actor_user_id,
                details={
                    "raw_score": attempt.raw_score,
                    "final_score": attempt.final_score,
                    "percentage": attempt.percentage,
                },
            )
        return first_time

    def maybe_send_grading_notification(
        self,
        attempt: TestAttempt,
        test: Test,
        *,
        became_graded_first_time: bool,
    ) -> None:
        """Send grading email once when attempt reaches GRADED for the first time."""
        if not became_graded_first_time:
            return
        if attempt.status != TestAttemptStatus.GRADED.value:
            return
        if attempt.grading_notification_sent_at is not None:
            return

        user = attempt.user
        if not user or not user.email:
            logger.warning(
                "Skipping grading notification attempt_id=%s — student email missing",
                attempt.id,
            )
            return

        student_name = getattr(user, "full_name", None) or user.email
        max_score = self.maximum_score(test)
        try:
            self.email.send_grading_completed_email(
                to_email=user.email,
                student_name=student_name,
                test_name=test.name,
                final_score=float(attempt.final_score or 0),
                maximum_score=max_score,
                percentage=float(attempt.percentage or 0),
            )
        except EmailDeliveryError:
            logger.exception(
                "Failed to send grading notification attempt_id=%s user_id=%s",
                attempt.id,
                attempt.user_id,
            )
            return

        now = datetime.now(timezone.utc)
        attempt.grading_notification_sent_at = now
        self._log_audit(
            attempt.id,
            AttemptGradingAuditAction.GRADING_NOTIFICATION_SENT.value,
            actor_user_id=attempt.user_id,
            details={"email": user.email},
        )

    def has_pending_review(self, attempt: TestAttempt) -> bool:
        for answer in self.answers.list_for_attempt(attempt.id):
            if answer.grading_status == AnswerGradingStatus.PENDING_REVIEW.value:
                return True
        return False

    def recompute_attempt_scores(self, attempt: TestAttempt, test: Test) -> None:
        total_earned = Decimal("0")
        for answer in self.answers.list_for_attempt(attempt.id):
            if answer.earned_score is not None:
                total_earned += Decimal(str(answer.earned_score))
        attempt.raw_score = float(total_earned)
        attempt.final_score = float(total_earned)
        max_score = self.maximum_score(test)
        if max_score > 0:
            attempt.percentage = round(
                float((total_earned / Decimal(str(max_score))) * Decimal("100")),
                2,
            )
        else:
            attempt.percentage = 0.0

    def maximum_score(self, test: Test) -> float:
        rows = self.test_questions.list_active_for_test(test.id)
        if rows:
            total = sum(Decimal(str(row.points or 0)) for row in rows)
            return float(total)
        if test.total_score is not None:
            return float(test.total_score)
        return 0.0

    def build_grading_result(self, attempt: TestAttempt, test: Test) -> dict:
        if attempt.status == TestAttemptStatus.SUBMITTED.value:
            return {
                "grading_completed": False,
                "message": "This attempt is waiting for manual grading.",
            }

        if attempt.status != TestAttemptStatus.GRADED.value:
            return {
                "grading_completed": False,
                "message": "Grading is not available for this attempt status.",
                "status": attempt.status,
            }

        return {
            "grading_completed": True,
            "final_score": attempt.final_score,
            "maximum_score": self.maximum_score(test),
            "percentage": round(float(attempt.percentage), 2)
            if attempt.percentage is not None
            else None,
            "grading_summary": self._grading_summary(attempt),
            "submitted_at": attempt.submitted_at.isoformat()
            if attempt.submitted_at
            else None,
            "graded_at": attempt.graded_at.isoformat() if attempt.graded_at else None,
        }

    def _run_initial_auto_grading(self, attempt: TestAttempt, test: Test) -> None:
        question_rows = {
            row.id: row
            for row in self.test_questions.list_active_for_test(test.id)
        }
        answers = self.answers.list_for_attempt(attempt.id)
        answered_question_ids = {answer.test_question_id for answer in answers}

        for answer in answers:
            test_question = question_rows.get(answer.test_question_id)
            if not test_question:
                continue
            self._apply_initial_grading_decision(test_question, answer)

        for question_id, test_question in question_rows.items():
            type_code = (test_question.snapshot_type_code or "").upper()
            if type_code != "ESSAY" or question_id in answered_question_ids:
                continue
            placeholder = AttemptAnswer(
                attempt_id=attempt.id,
                test_question_id=question_id,
                is_correct=None,
                earned_score=None,
                grading_status=AnswerGradingStatus.PENDING_REVIEW.value,
            )
            self.answers.add(placeholder)

        self.recompute_attempt_scores(attempt, test)

    def _apply_initial_grading_decision(
        self, test_question: TestQuestion, answer: AttemptAnswer
    ) -> None:
        type_code = (test_question.snapshot_type_code or "").upper()
        if type_code == "ESSAY":
            answer.is_correct = None
            answer.earned_score = None
            answer.grading_status = AnswerGradingStatus.PENDING_REVIEW.value
            return
        if type_code not in _OBJECTIVE_TYPES:
            answer.is_correct = None
            answer.earned_score = None
            answer.grading_status = AnswerGradingStatus.PENDING_REVIEW.value
            return

        is_correct, earned = self._grade_objective_answer(test_question, answer)
        answer.is_correct = is_correct
        answer.earned_score = earned
        answer.grading_status = AnswerGradingStatus.AUTO_GRADED.value

    def _grade_objective_answer(
        self, test_question: TestQuestion, answer: AttemptAnswer
    ) -> tuple[bool | None, Decimal | None]:
        type_code = (test_question.snapshot_type_code or "").upper()
        choices = self._load_json(test_question.snapshot_choices_json) or []
        indices = answer.get_selected_indices()
        max_points = Decimal(str(test_question.points or 0))

        if type_code in ("MCQ", "TRUE_FALSE"):
            if len(indices) != 1:
                return False, Decimal("0")
            idx = indices[0]
            if idx < 0 or idx >= len(choices):
                return False, Decimal("0")
            correct = bool(choices[idx].get("is_correct"))
            return correct, max_points if correct else Decimal("0")

        if type_code == "MULTI_SELECT":
            correct_indices = {
                i for i, choice in enumerate(choices) if choice.get("is_correct")
            }
            selected = set(indices)
            if selected == correct_indices and correct_indices:
                return True, max_points
            return False, Decimal("0")

        return None, None

    def _pending_answers_by_question(
        self, attempt: TestAttempt
    ) -> dict[int, AttemptAnswer]:
        return {
            answer.test_question_id: answer
            for answer in self.answers.list_for_attempt(attempt.id)
            if answer.grading_status == AnswerGradingStatus.PENDING_REVIEW.value
        }

    def _grading_summary(self, attempt: TestAttempt) -> dict:
        counts = {
            AnswerGradingStatus.AUTO_GRADED.value: 0,
            AnswerGradingStatus.PENDING_REVIEW.value: 0,
            AnswerGradingStatus.MANUALLY_GRADED.value: 0,
        }
        for answer in self.answers.list_for_attempt(attempt.id):
            status = answer.grading_status
            if status in counts:
                counts[status] += 1
        return {
            "total_answers": sum(counts.values()),
            "auto_graded": counts[AnswerGradingStatus.AUTO_GRADED.value],
            "pending_review": counts[AnswerGradingStatus.PENDING_REVIEW.value],
            "manually_graded": counts[AnswerGradingStatus.MANUALLY_GRADED.value],
        }

    def _log_audit(
        self,
        attempt_id: int,
        action: str,
        *,
        actor_membership_id: int | None = None,
        actor_user_id: int | None = None,
        details: dict | None = None,
    ) -> None:
        payload = json.dumps(details) if details is not None else None
        self.audit.add_log(
            attempt_id=attempt_id,
            action=action,
            actor_membership_id=actor_membership_id,
            actor_user_id=actor_user_id,
            details=payload,
        )
        logger.info(
            "event=grading_audit attempt_id=%s action=%s actor_membership_id=%s",
            attempt_id,
            action,
            actor_membership_id,
        )

    def _load_json(self, value):
        if not value:
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return None
