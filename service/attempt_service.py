"""
Exam attempt runtime — start, resume, autosave, submit, timeout, grading.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from flask import current_app

from models import AttemptAnswer, Test, TestAttempt, TestQuestion
from repositories.attempt_repository import (
    AttemptAnswerRepository,
    TestAttemptRepository,
    TestQuestionRepositoryExtended,
)
from repositories.subject_repository import SubjectMembershipRepository, SubjectRepository
from repositories.test_assignment_repository import TestStudentAssignmentRepository
from repositories.test_repository import TestRepository
from repositories.workspace_repository import WorkspaceRepository
from service.exam_grading_service import ExamGradingService
from service.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from utils.academic_rbac import (
    can_manage_test_attempts,
    can_take_published_test,
    can_view_attempt_grading,
    verify_subject_student_access,
)
from utils.app_timezone import ensure_local_aware, format_local_datetime, local_timezone_now
from utils.db import db
from utils.enums import (
    AttemptSubmissionSource,
    AvailabilityTimeMode,
    MembershipRole,
    TestAttemptStatus,
    TestStatus,
)

logger = logging.getLogger(__name__)

_OBJECTIVE_TYPES = frozenset({"MCQ", "TRUE_FALSE", "MULTI_SELECT"})


class AttemptService:
    def __init__(self):
        self.attempts = TestAttemptRepository()
        self.answers = AttemptAnswerRepository()
        self.test_questions = TestQuestionRepositoryExtended()
        self.tests = TestRepository()
        self.grading = ExamGradingService()
        self.subjects = SubjectRepository()
        self.subject_memberships = SubjectMembershipRepository()
        self.test_assignments = TestStudentAssignmentRepository()
        self.workspaces = WorkspaceRepository()

    def list_available_tests(
        self, *, workspace_id: int, actor_membership
    ) -> list[dict]:
        workspace = self._get_workspace(workspace_id)
        subject_ids = self._student_subject_ids(actor_membership.id, workspace_id)
        if not subject_ids and actor_membership.role != MembershipRole.ADMIN.value:
            if not self._is_workspace_manager(workspace, actor_membership):
                return []

        if self._is_workspace_manager(workspace, actor_membership):
            from utils.enums import TestStatus as TS

            rows = list(
                db.session.execute(
                    db.select(Test)
                    .where(
                        Test.status == TS.PUBLISHED.value,
                        Test.created_by.has(workspace_id=workspace_id),
                    )
                    .order_by(Test.published_at.desc().nullslast(), Test.id.desc())
                ).scalars().all()
            )
        else:
            rows = self.attempts.list_published_for_subjects(
                subject_ids,
                workspace_id,
                actor_membership.id,
            )

        return [self._serialize_test_summary(test) for test in rows]

    def start_or_resume_attempt(
        self,
        *,
        test_id: int,
        workspace_id: int,
        actor_membership,
        actor_user_id: int,
    ) -> dict:
        test, _ = self._resolve_student_test_access(test_id, workspace_id, actor_membership)
        existing = self.attempts.find_active_for_student(test.id, actor_membership.id)
        if existing:
            self._ensure_resume_allowed(existing, test)
            self._check_and_apply_timeout(existing, test)
            if existing.status == TestAttemptStatus.IN_PROGRESS.value:
                existing.last_activity_at = local_timezone_now()
                db.session.commit()
                deadline = self._attempt_end_deadline(existing, test)
                if deadline:
                    remaining_minutes = max(
                        0.0, (deadline - local_timezone_now()).total_seconds() / 60
                    )
                    if self._is_flexible(test):
                        logger.info(
                            "[FLEXIBLE] Attempt resumed attempt_id=%s ends_at=%s "
                            "remaining_minutes=%.1f",
                            existing.id,
                            deadline.isoformat(),
                            remaining_minutes,
                        )
                    else:
                        logger.info(
                            "[SCHEDULED] Attempt resumed attempt_id=%s global_end=%s "
                            "remaining_minutes=%.1f",
                            existing.id,
                            deadline.isoformat(),
                            remaining_minutes,
                        )
                logger.info(
                    "event=attempt_resumed attempt_id=%s test_id=%s student_membership_id=%s result=success",
                    existing.id,
                    test.id,
                    actor_membership.id,
                )
                return {
                    "message": "Attempt resumed",
                    "attempt": self.serialize_attempt(existing, include_answers=True),
                    "resumed": True,
                }

        if self.attempts.find_completed_for_student(test.id, actor_membership.id):
            completed_count = self.attempts.count_completed_for_student(
                test.id, actor_membership.id
            )
            max_attempts = self._max_attempts(test)
            if completed_count >= max_attempts:
                raise ConflictError(
                    f"You have reached the maximum allowed attempts ({max_attempts})"
                )

        self._ensure_test_takeable_for_first_attempt(test)

        now = local_timezone_now()
        expires_at = self._compute_attempt_expires_at(test, now)

        attempt = TestAttempt(
            test_id=test.id,
            student_membership_id=actor_membership.id,
            user_id=actor_user_id,
            status=TestAttemptStatus.IN_PROGRESS.value,
            started_at=now,
            last_activity_at=now,
            expires_at=expires_at,
        )
        self.attempts.add(attempt)
        db.session.commit()
        if self._is_flexible(test):
            logger.info(
                "[FLEXIBLE] Attempt started attempt_id=%s test_id=%s student_membership_id=%s "
                "ends_at=%s duration_minutes=%s",
                attempt.id,
                test.id,
                actor_membership.id,
                expires_at.isoformat(),
                test.duration_minutes,
            )
        else:
            logger.info(
                "[SCHEDULED] Attempt started attempt_id=%s test_id=%s global_end=%s",
                attempt.id,
                test.id,
                expires_at.isoformat(),
            )
        self._maybe_start_proctoring(
            attempt=attempt,
            test=test,
            workspace_id=workspace_id,
        )
        logger.info(
            "event=attempt_created attempt_id=%s test_id=%s student_membership_id=%s result=success",
            attempt.id,
            test.id,
            actor_membership.id,
        )
        return {
            "message": "Attempt started",
            "attempt": self.serialize_attempt(attempt, include_answers=True),
            "resumed": False,
        }

    def get_current_attempt(
        self, *, test_id: int, workspace_id: int, actor_membership
    ) -> dict:
        test, _ = self._resolve_student_test_access(
            test_id, workspace_id, actor_membership
        )
        attempt = self.attempts.find_active_for_student(test.id, actor_membership.id)
        if not attempt:
            raise NotFoundError("No in-progress attempt for this test")
        self._check_and_apply_timeout(attempt, test)
        if attempt.status != TestAttemptStatus.IN_PROGRESS.value:
            raise NotFoundError("No in-progress attempt for this test")
        return {
            "attempt": self.serialize_attempt(attempt, include_answers=True),
        }

    def get_attempt(
        self,
        *,
        test_id: int,
        attempt_id: int,
        workspace_id: int,
        actor_membership,
        student_view: bool = False,
    ) -> dict:
        attempt = self._get_attempt_or_404(attempt_id, test_id)
        test = self._get_test_in_workspace(test_id, workspace_id)
        self._ensure_attempt_access(
            attempt, test, workspace_id, actor_membership, student_view=student_view
        )
        self._check_and_apply_timeout(attempt, test)
        strip = student_view or attempt.student_membership_id == actor_membership.id
        return {
            "attempt": self.serialize_attempt(
                attempt,
                include_answers=True,
                student_view=strip,
            ),
        }

    def list_test_attempts(
        self, *, test_id: int, workspace_id: int, actor_membership
    ) -> list[dict]:
        test = self._get_test_in_workspace(test_id, workspace_id)
        self._ensure_teacher_attempt_access(test, workspace_id, actor_membership)
        rows = self.attempts.list_for_test(test.id)
        return [self.serialize_attempt(row, include_answers=False) for row in rows]

    def save_answers(
        self,
        *,
        test_id: int,
        attempt_id: int,
        workspace_id: int,
        actor_membership,
        answers: list[dict],
    ) -> dict:
        attempt, test = self._resolve_in_progress_attempt(
            test_id, attempt_id, workspace_id, actor_membership
        )
        saved = self._upsert_answers(attempt, test, answers)
        attempt.last_activity_at = datetime.now(timezone.utc)
        db.session.commit()
        logger.info(
            "Autosaved %s answer(s) for attempt id=%s",
            len(saved),
            attempt.id,
        )
        return {
            "message": "Answers saved",
            "answers": [self._serialize_answer(a) for a in saved],
            "count": len(saved),
        }

    def update_answer(
        self,
        *,
        test_id: int,
        attempt_id: int,
        test_question_id: int,
        workspace_id: int,
        actor_membership,
        data: dict,
    ) -> dict:
        attempt, test = self._resolve_in_progress_attempt(
            test_id, attempt_id, workspace_id, actor_membership
        )
        saved = self._upsert_answers(
            attempt,
            test,
            [{"test_question_id": test_question_id, **data}],
        )
        attempt.last_activity_at = datetime.now(timezone.utc)
        db.session.commit()
        if not saved:
            raise NotFoundError("Test question not found in this exam")
        logger.info(
            "Updated answer for attempt id=%s test_question_id=%s",
            attempt.id,
            test_question_id,
        )
        return {
            "message": "Answer updated",
            "answer": self._serialize_answer(saved[0]),
        }

    def submit_attempt(
        self,
        *,
        test_id: int,
        attempt_id: int,
        workspace_id: int,
        actor_membership,
        submission_source: str = AttemptSubmissionSource.STUDENT.value,
    ) -> dict:
        attempt = self._get_attempt_or_404(attempt_id, test_id)
        test = self._get_test_in_workspace(test_id, workspace_id)

        if submission_source == AttemptSubmissionSource.FORCE.value:
            self._ensure_teacher_attempt_access(test, workspace_id, actor_membership)
        else:
            if attempt.student_membership_id != actor_membership.id:
                raise ForbiddenError("You can only submit your own attempt")
            self._resolve_student_test_access(test_id, workspace_id, actor_membership)

        self._check_and_apply_timeout(attempt, test)
        if attempt.status != TestAttemptStatus.IN_PROGRESS.value:
            raise ConflictError("Attempt is not in progress")
        self._validate_submission_answer_rules(attempt, test)

        result = self._finalize_attempt(
            attempt, test, submission_source=submission_source
        )
        return {
            "message": "Attempt submitted",
            **result,
        }

    def force_submit_attempt(
        self, *, test_id: int, attempt_id: int, workspace_id: int, actor_membership
    ) -> dict:
        result = self.submit_attempt(
            test_id=test_id,
            attempt_id=attempt_id,
            workspace_id=workspace_id,
            actor_membership=actor_membership,
            submission_source=AttemptSubmissionSource.FORCE.value,
        )
        result["message"] = "Attempt force-submitted"
        return result

    def grade_attempt_essays(
        self,
        *,
        test_id: int,
        attempt_id: int,
        workspace_id: int,
        actor_membership,
        grades: list[dict],
    ) -> dict:
        attempt = self._get_attempt_or_404(attempt_id, test_id)
        test = self._get_test_in_workspace(test_id, workspace_id)
        self._ensure_teacher_attempt_access(test, workspace_id, actor_membership)

        if attempt.status != TestAttemptStatus.SUBMITTED.value:
            raise ValidationError(
                "Manual grading is only available while the attempt is awaiting review"
            )

        message, became_graded = self.grading.grade_pending_answers(
            attempt,
            test,
            grades,
            actor_membership_id=actor_membership.id,
            actor_user_id=actor_membership.user_id,
        )
        self.grading.maybe_send_grading_notification(
            attempt,
            test,
            became_graded_first_time=became_graded,
        )

        db.session.commit()
        logger.info(
            "event=manual_grading attempt_id=%s test_id=%s actor_membership_id=%s status=%s",
            attempt.id,
            test.id,
            actor_membership.id,
            attempt.status,
        )
        return {
            "message": message,
            "attempt": self.serialize_attempt(attempt, include_answers=True),
        }

    def get_grading_result(
        self,
        *,
        test_id: int,
        attempt_id: int,
        workspace_id: int,
        actor_membership,
    ) -> dict:
        attempt = self._get_attempt_or_404(attempt_id, test_id)
        test = self._get_test_in_workspace(test_id, workspace_id)
        if attempt.student_membership_id == actor_membership.id:
            self._resolve_student_test_access(test.id, workspace_id, actor_membership)
        else:
            workspace = self._get_workspace(workspace_id)
            actor_link = self.subject_memberships.find_active(
                actor_membership.id, test.subject_id
            )
            is_creator = test.created_by_membership_id == actor_membership.id
            if not can_view_attempt_grading(
                workspace,
                actor_membership,
                actor_subject_link=actor_link,
                is_test_creator=is_creator,
            ):
                raise ForbiddenError(
                    "Insufficient permissions to view this attempt's grading result"
                )
        if attempt.status == TestAttemptStatus.IN_PROGRESS.value:
            raise ValidationError("Grading results are available only after submission")
        return self.grading.build_grading_result(attempt, test)

    def timeout_attempt(
        self, *, test_id: int, attempt_id: int, workspace_id: int, actor_membership
    ) -> dict:
        return self.submit_attempt(
            test_id=test_id,
            attempt_id=attempt_id,
            workspace_id=workspace_id,
            actor_membership=actor_membership,
            submission_source=AttemptSubmissionSource.TIMEOUT.value,
        )

    def auto_submit_due_attempts(self) -> list[int]:
        now = local_timezone_now()
        due_attempt_ids: list[int] = []
        rows = self.attempts.list_in_progress_on_published_tests()
        for attempt in rows:
            test = attempt.test or self.tests.get_by_id(attempt.test_id)
            if not test:
                continue
            deadline = self._attempt_end_deadline(attempt, test)
            if not deadline or now < deadline:
                continue
            mode_label = "FLEXIBLE" if self._is_flexible(test) else "SCHEDULED"
            logger.info(
                "[%s] Auto-submit attempt_id=%s test_id=%s deadline=%s",
                mode_label,
                attempt.id,
                test.id,
                deadline.isoformat(),
            )
            self._finalize_attempt(
                attempt,
                test,
                submission_source=AttemptSubmissionSource.TIMEOUT.value,
            )
            due_attempt_ids.append(attempt.id)
        if due_attempt_ids:
            logger.info(
                "event=auto_submission_batch count=%s attempt_ids=%s result=success",
                len(due_attempt_ids),
                due_attempt_ids,
            )
        return due_attempt_ids

    def _finalize_attempt(
        self,
        attempt: TestAttempt,
        test: Test,
        *,
        submission_source: str,
    ) -> dict:
        if attempt.status != TestAttemptStatus.IN_PROGRESS.value:
            raise ConflictError("Attempt is already finalized")

        now = datetime.now(timezone.utc)
        attempt.status = TestAttemptStatus.SUBMITTED.value
        attempt.submitted_at = now
        attempt.last_activity_at = now
        attempt.submission_source = submission_source

        became_graded = self.grading.process_submission_grading(
            attempt,
            test,
            submission_source=submission_source,
            actor_membership_id=attempt.student_membership_id,
            actor_user_id=attempt.user_id,
        )
        self.grading.maybe_send_grading_notification(
            attempt,
            test,
            became_graded_first_time=became_graded,
        )

        self._maybe_terminate_proctoring(attempt=attempt, completed=True)

        db.session.commit()
        logger.info(
            "Finalized attempt id=%s source=%s status=%s raw_score=%s",
            attempt.id,
            submission_source,
            attempt.status,
            attempt.raw_score,
        )
        return {
            "attempt": self.serialize_attempt(attempt, include_answers=True),
        }

    def _upsert_answers(
        self,
        attempt: TestAttempt,
        test: Test,
        payloads: list[dict],
    ) -> list[AttemptAnswer]:
        if not payloads:
            return []

        question_ids = [int(item["test_question_id"]) for item in payloads]
        question_map = self.test_questions.map_ids_for_test(test.id, question_ids)
        saved: list[AttemptAnswer] = []

        for item in payloads:
            test_question_id = int(item["test_question_id"])
            test_question = question_map.get(test_question_id)
            if not test_question:
                raise NotFoundError(
                    f"Test question {test_question_id} not found in this exam"
                )

            row = self.answers.find_by_attempt_and_test_question(
                attempt.id, test_question_id
            )
            if not row:
                row = AttemptAnswer(
                    attempt_id=attempt.id,
                    test_question_id=test_question_id,
                )
                self.answers.add(row)

            self._apply_answer_payload(row, test_question, item)
            saved.append(row)

        return saved

    def _apply_answer_payload(
        self,
        answer: AttemptAnswer,
        test_question: TestQuestion,
        data: dict,
    ) -> None:
        type_code = (test_question.snapshot_type_code or "").upper()

        if "answer_text" in data:
            answer.answer_text = (data.get("answer_text") or "").strip() or None

        if "selected_choice_indices" in data:
            indices = data.get("selected_choice_indices")
            if indices is None:
                answer.set_selected_indices([])
            elif isinstance(indices, list):
                answer.set_selected_indices(indices)
            else:
                raise ValidationError("selected_choice_indices must be an array of integers")

        if type_code in _OBJECTIVE_TYPES and not answer.get_selected_indices():
            if answer.answer_text:
                raise ValidationError(
                    f"{type_code} questions require selected_choice_indices"
                )

        if type_code == "ESSAY" and answer.get_selected_indices():
            raise ValidationError("ESSAY questions cannot include selected_choice_indices")

    def _check_and_apply_timeout(self, attempt: TestAttempt, test: Test) -> None:
        if attempt.status != TestAttemptStatus.IN_PROGRESS.value:
            return
        deadline = self._attempt_end_deadline(attempt, test)
        if not deadline:
            return
        now = local_timezone_now()
        if now >= deadline:
            mode_label = "FLEXIBLE" if self._is_flexible(test) else "SCHEDULED"
            logger.info(
                "[%s] Timeout reached attempt_id=%s test_id=%s deadline=%s",
                mode_label,
                attempt.id,
                attempt.test_id,
                deadline.isoformat(),
            )
            self._finalize_attempt(
                attempt,
                test,
                submission_source=AttemptSubmissionSource.TIMEOUT.value,
            )

    def _availability_mode(self, test: Test) -> str:
        return (
            test.availability_time_mode or AvailabilityTimeMode.SCHEDULED.value
        ).upper()

    def _is_flexible(self, test: Test) -> bool:
        return self._availability_mode(test) == AvailabilityTimeMode.FLEXIBLE.value

    def _is_scheduled(self, test: Test) -> bool:
        return not self._is_flexible(test)

    def _scheduled_global_end_time(self, test: Test) -> datetime | None:
        if not test.starts_at or not test.duration_minutes:
            return None
        return ensure_local_aware(test.starts_at) + timedelta(
            minutes=int(test.duration_minutes)
        )

    def _attempt_end_deadline(
        self, attempt: TestAttempt, test: Test
    ) -> datetime | None:
        if self._is_flexible(test):
            if not attempt.expires_at:
                return None
            return ensure_local_aware(attempt.expires_at)
        return self._scheduled_global_end_time(test)

    def _compute_attempt_expires_at(
        self, test: Test, started_at: datetime
    ) -> datetime:
        if not test.duration_minutes:
            raise ValidationError("Test duration is not configured")
        if self._is_flexible(test):
            ends_at = ensure_local_aware(started_at) + timedelta(
                minutes=int(test.duration_minutes)
            )
            logger.info(
                "[FLEXIBLE] Attempt ends at %s (duration_minutes=%s)",
                ends_at.isoformat(),
                test.duration_minutes,
            )
            return ends_at
        global_end = self._scheduled_global_end_time(test)
        if not global_end:
            raise ValidationError(
                "Test starts_at and duration_minutes are required for scheduled exams"
            )
        logger.info("[SCHEDULED] Global end %s", global_end.isoformat())
        return global_end

    def _ensure_test_takeable_for_first_attempt(self, test: Test) -> None:
        if test.status != TestStatus.PUBLISHED.value:
            raise ValidationError("Test is not published")
        if not test.duration_minutes:
            raise ValidationError("Test duration is not configured")

        if self._is_flexible(test):
            logger.info(
                "[FLEXIBLE] Exam available for first attempt test_id=%s",
                test.id,
            )
            return

        now = local_timezone_now()
        if not test.starts_at:
            raise ValidationError("Test start time is not configured")
        starts_at = ensure_local_aware(test.starts_at)
        if now < starts_at:
            raise ValidationError("Test has not started yet")
        global_end = self._scheduled_global_end_time(test)
        if global_end and now >= global_end:
            raise ForbiddenError("Exam has already ended")
        if test.entry_window_minutes:
            window_end = starts_at + timedelta(
                minutes=int(test.entry_window_minutes)
            )
            if now > window_end:
                logger.info(
                    "event=entry_window_rejected test_id=%s reason=window_closed result=forbidden",
                    test.id,
                )
                raise ForbiddenError("Entry window has closed.")
        logger.info(
            "[SCHEDULED] Global end %s",
            global_end.isoformat() if global_end else "n/a",
        )

    def _ensure_resume_allowed(self, attempt: TestAttempt, test: Test) -> None:
        if attempt.status != TestAttemptStatus.IN_PROGRESS.value:
            raise ConflictError("Attempt is not in progress")
        if test.status != TestStatus.PUBLISHED.value:
            raise ForbiddenError("Exam is no longer available for resume")
        deadline = self._attempt_end_deadline(attempt, test)
        if deadline and local_timezone_now() >= deadline:
            raise ForbiddenError("Exam has already ended")

    def serialize_attempt(
        self,
        attempt: TestAttempt,
        *,
        include_answers: bool = True,
        student_view: bool = False,
    ) -> dict:
        test = attempt.test or self.tests.get_by_id(attempt.test_id)
        now = local_timezone_now()
        deadline = self._attempt_end_deadline(attempt, test) if test else None
        global_end = (
            self._scheduled_global_end_time(test)
            if test and self._is_scheduled(test)
            else None
        )
        remaining_seconds = None
        if deadline:
            remaining_seconds = max(0, int((deadline - now).total_seconds()))

        payload = {
            "id": attempt.id,
            "test_id": attempt.test_id,
            "student_membership_id": attempt.student_membership_id,
            "user_id": attempt.user_id,
            "status": attempt.status,
            "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
            "submitted_at": attempt.submitted_at.isoformat()
            if attempt.submitted_at
            else None,
            "expires_at": attempt.expires_at.isoformat() if attempt.expires_at else None,
            "last_activity_at": attempt.last_activity_at.isoformat()
            if attempt.last_activity_at
            else None,
            "submission_source": attempt.submission_source,
            "raw_score": attempt.raw_score,
            "final_score": attempt.final_score,
            "percentage": attempt.percentage,
            "graded_at": attempt.graded_at.isoformat() if attempt.graded_at else None,
            "requires_manual_grading": self.grading.has_pending_review(attempt),
            "availability_time_mode": self._availability_mode(test) if test else None,
            "global_end_at": global_end.isoformat() if global_end else None,
            "remaining_seconds": remaining_seconds,
        }

        if include_answers:
            question_rows = (
                self.test_questions.list_active_for_test(test.id) if test else []
            )
            answer_map = {
                answer.test_question_id: answer
                for answer in self.answers.list_for_attempt(attempt.id)
            }
            payload["questions"] = [
                self._serialize_runtime_question(
                    row,
                    answer_map.get(row.id),
                    student_view=student_view,
                )
                for row in question_rows
            ]
            payload["answers"] = [
                self._serialize_answer(answer_map[q.id])
                for q in question_rows
                if q.id in answer_map
            ]
        return payload

    def _serialize_runtime_question(
        self,
        row: TestQuestion,
        answer: AttemptAnswer | None,
        *,
        student_view: bool,
    ) -> dict:
        choices = self._load_json(row.snapshot_choices_json) or []
        if student_view:
            choices = [
                {
                    "index": idx,
                    "body": choice.get("body"),
                    "order_index": choice.get("order_index", idx),
                }
                for idx, choice in enumerate(choices)
            ]
        else:
            choices = [
                {
                    "index": idx,
                    **choice,
                }
                for idx, choice in enumerate(choices)
            ]

        payload = {
            "test_question_id": row.id,
            "question_id": row.question_id,
            "source_type": row.source_type,
            "points": float(row.points) if row.points is not None else None,
            "snapshot_question_text": row.snapshot_question_text,
            "snapshot_type_code": row.snapshot_type_code,
            "snapshot_topic_name": row.snapshot_topic_name,
            "snapshot_difficulty": row.snapshot_difficulty,
            "choices": choices,
        }
        if answer:
            payload["answer"] = self._serialize_answer(answer)
        return payload

    def _serialize_answer(self, answer: AttemptAnswer) -> dict:
        return {
            "id": answer.id,
            "attempt_id": answer.attempt_id,
            "test_question_id": answer.test_question_id,
            "answer_text": answer.answer_text,
            "selected_choice_indices": answer.get_selected_indices(),
            "is_correct": answer.is_correct,
            "earned_score": float(answer.earned_score)
            if answer.earned_score is not None
            else None,
            "grading_status": answer.grading_status,
            "teacher_feedback": answer.teacher_feedback,
            "updated_at": answer.updated_at.isoformat() if answer.updated_at else None,
        }

    def _serialize_test_summary(self, test: Test) -> dict:
        return {
            "test_id": test.id,
            "name": test.name,
            "slug": test.slug,
            "description": test.description,
            "subject_id": test.subject_id,
            "status": test.status,
            "duration_minutes": test.duration_minutes,
            "total_score": float(test.total_score) if test.total_score is not None else None,
            "passing_score": float(test.passing_score)
            if test.passing_score is not None
            else None,
            "starts_at": format_local_datetime(test.starts_at),
            "published_at": format_local_datetime(test.published_at),
        }

    def _max_attempts(self, test: Test) -> int:
        settings = self._load_json(test.settings_config) or {}
        attempt_settings = settings.get("attempt_settings") or {}
        raw = attempt_settings.get("max_attempts")
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = 1
        return max(1, value)

    def _validate_submission_answer_rules(
        self, attempt: TestAttempt, test: Test
    ) -> None:
        settings = self._load_json(test.settings_config) or {}
        rules = settings.get("answer_rules") or {}
        require_all = bool(rules.get("require_answer_all", False))
        allow_skip = bool(rules.get("allow_skip_questions", True))
        if not require_all and allow_skip:
            return

        question_rows = self.test_questions.list_active_for_test(test.id)
        answer_map = {
            answer.test_question_id: answer
            for answer in self.answers.list_for_attempt(attempt.id)
        }
        missing_question_ids: list[int] = []
        for question in question_rows:
            answer = answer_map.get(question.id)
            if not answer:
                missing_question_ids.append(question.id)
                continue
            type_code = (question.snapshot_type_code or "").upper()
            if type_code == "ESSAY":
                if not (answer.answer_text or "").strip():
                    missing_question_ids.append(question.id)
                continue
            if not answer.get_selected_indices():
                missing_question_ids.append(question.id)

        if missing_question_ids:
            raise ValidationError(
                "All questions must be answered before submission. "
                f"Missing answers for question IDs: {missing_question_ids}"
            )

    def _resolve_in_progress_attempt(
        self,
        test_id: int,
        attempt_id: int,
        workspace_id: int,
        actor_membership,
    ) -> tuple[TestAttempt, Test]:
        attempt = self._get_attempt_or_404(attempt_id, test_id)
        test = self._get_test_in_workspace(test_id, workspace_id)
        if attempt.student_membership_id != actor_membership.id:
            raise ForbiddenError("You can only modify your own attempt")
        self._resolve_student_test_access(test_id, workspace_id, actor_membership)
        self._check_and_apply_timeout(attempt, test)
        if attempt.status != TestAttemptStatus.IN_PROGRESS.value:
            raise ConflictError("Attempt is not in progress")
        return attempt, test

    def _resolve_student_test_access(
        self, test_id: int, workspace_id: int, actor_membership
    ):
        test = self._get_test_in_workspace(test_id, workspace_id)
        workspace = self._get_workspace(workspace_id)
        actor_link = self.subject_memberships.find_active(
            actor_membership.id, test.subject_id
        )
        if not can_take_published_test(workspace, actor_membership, actor_link):
            raise ForbiddenError("You are not enrolled in this test's subject")
        if actor_membership.role == MembershipRole.STUDENT.value:
            if not verify_subject_student_access(actor_link):
                raise ForbiddenError("Only students enrolled in the subject can take tests")
            assignment = self.test_assignments.find(
                test_id=test.id,
                student_membership_id=actor_membership.id,
            )
            if not assignment:
                raise ForbiddenError("You are not assigned to this exam")
        return test, actor_link

    def _ensure_attempt_access(
        self,
        attempt: TestAttempt,
        test: Test,
        workspace_id: int,
        actor_membership,
        *,
        student_view: bool,
    ) -> None:
        if attempt.student_membership_id == actor_membership.id:
            self._resolve_student_test_access(test.id, workspace_id, actor_membership)
            return
        if student_view:
            raise ForbiddenError("Cannot view another student's attempt in student mode")
        self._ensure_teacher_attempt_access(test, workspace_id, actor_membership)

    def _ensure_teacher_attempt_access(
        self, test: Test, workspace_id: int, actor_membership
    ) -> None:
        workspace = self._get_workspace(workspace_id)
        actor_link = self.subject_memberships.find_active(
            actor_membership.id, test.subject_id
        )
        is_creator = test.created_by_membership_id == actor_membership.id
        if not can_manage_test_attempts(
            workspace,
            actor_membership,
            actor_subject_link=actor_link,
            is_test_creator=is_creator,
        ):
            raise ForbiddenError("Insufficient permissions to manage attempts")

    def _student_subject_ids(
        self, membership_id: int, workspace_id: int
    ) -> list[int]:
        from models import Subject, SubjectMembership
        from utils.enums import SubjectMembershipStatus, SubjectRole

        rows = db.session.execute(
            db.select(SubjectMembership.subject_id)
            .join(Subject, Subject.id == SubjectMembership.subject_id)
            .where(
                SubjectMembership.membership_id == membership_id,
                Subject.workspace_id == workspace_id,
                SubjectMembership.subject_role == SubjectRole.STUDENT.value,
                SubjectMembership.status == SubjectMembershipStatus.ACTIVE.value,
                SubjectMembership.deleted_at.is_(None),
                Subject.deleted_at.is_(None),
            )
        ).scalars().all()
        return list(rows)

    def _is_workspace_manager(self, workspace, membership) -> bool:
        from utils.rbac import can_manage_workspace_settings

        return can_manage_workspace_settings(workspace, membership)

    def _get_workspace(self, workspace_id: int):
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")
        return workspace

    def _get_test_in_workspace(self, test_id: int, workspace_id: int) -> Test:
        test = self.tests.get_by_id_in_workspace(test_id, workspace_id)
        if not test:
            raise NotFoundError("Test not found")
        return test

    def _get_attempt_or_404(self, attempt_id: int, test_id: int) -> TestAttempt:
        attempt = self.attempts.get_for_test(attempt_id, test_id)
        if not attempt:
            raise NotFoundError("Attempt not found")
        return attempt

    def _maybe_start_proctoring(
        self, *, attempt: TestAttempt, test: Test, workspace_id: int
    ) -> None:
        from service.proctoring_service import ProctoringService

        try:
            ProctoringService().ensure_session_for_attempt(
                test_attempt=attempt,
                workspace_id=workspace_id,
                test=test,
            )
        except Exception:
            logger.exception(
                "Failed to auto-start proctoring for attempt id=%s", attempt.id
            )

    def _maybe_terminate_proctoring(self, *, attempt: TestAttempt, completed: bool) -> None:
        from service.proctoring_service import ProctoringService

        try:
            ProctoringService().terminate_session_for_attempt(
                test_attempt_id=attempt.id,
                completed=completed,
                actor_user_id=attempt.user_id,
            )
        except Exception:
            logger.exception(
                "Failed to terminate proctoring for attempt id=%s", attempt.id
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
