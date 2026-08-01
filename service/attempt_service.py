"""
Exam attempt runtime — start, resume, autosave, submit, timeout, grading.
"""

from __future__ import annotations

from utils.messages import Messages

import json
import logging
from datetime import datetime, timedelta, timezone

from flask import current_app

from sqlalchemy.orm import joinedload

from models import AttemptAnswer, Membership, Test, TestAttempt, TestQuestion
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
    AttemptTerminationReason,
    AvailabilityTimeMode,
    MembershipRole,
    TestAttemptStatus,
    TestStatus,
)
from utils.pagination import build_pagination_meta, normalize_pagination

logger = logging.getLogger(__name__)

_OBJECTIVE_TYPES = frozenset({"MCQ", "TRUE_FALSE", "MULTI_SELECT"})

# Student dashboard Recent Exams UI statuses (mapped from attempt status only).
_RECENT_STATUS_GRADED = "GRADED"
_RECENT_STATUS_PENDING_GRADING = "PENDING_GRADING"

# Student exam hub lifecycle statuses (GET /student/tests).
_LIFECYCLE_UPCOMING = "UPCOMING"
_LIFECYCLE_IN_PROGRESS = "IN_PROGRESS"
_LIFECYCLE_PENDING_GRADING = "PENDING_GRADING"
_LIFECYCLE_GRADED = "GRADED"

_LIFECYCLE_SORT_ORDER = {
    _LIFECYCLE_IN_PROGRESS: 0,
    _LIFECYCLE_PENDING_GRADING: 1,
    _LIFECYCLE_GRADED: 2,
    _LIFECYCLE_UPCOMING: 3,
}


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
                    .options(
                        joinedload(Test.created_by).joinedload(Membership.user),
                    )
                    .where(
                        Test.status == TS.PUBLISHED.value,
                        Test.created_by.has(workspace_id=workspace_id),
                    )
                    .order_by(Test.published_at.desc().nullslast(), Test.id.desc())
                )
                .scalars()
                .unique()
                .all()
            )
        else:
            rows = self.attempts.list_published_for_subjects(
                subject_ids,
                workspace_id,
                actor_membership.id,
            )

        return [self._serialize_test_summary(test) for test in rows]

    def list_upcoming_tests(
        self, *, workspace_id: int, actor_membership
    ) -> list[dict]:
        subject_ids = self._student_subject_ids(actor_membership.id, workspace_id)
        rows = self.attempts.list_published_for_subjects(
            subject_ids,
            workspace_id,
            actor_membership.id,
        )
        if not rows:
            return []

        test_ids = [test.id for test in rows]
        blocked_ids = self.attempts.find_test_ids_with_attempt_statuses(
            test_ids,
            actor_membership.id,
            [
                TestAttemptStatus.IN_PROGRESS.value,
                TestAttemptStatus.SUBMITTED.value,
                TestAttemptStatus.GRADED.value,
            ],
        )

        now = local_timezone_now()
        upcoming: list[tuple[tuple, dict]] = []
        for test in rows:
            if test.id in blocked_ids:
                continue
            if test.status != TestStatus.PUBLISHED.value or test.archived_at is not None:
                continue
            if self._is_upcoming_window_closed(test, now):
                continue
            payload = self._serialize_upcoming_test(test, now)
            upcoming.append((self._upcoming_sort_key(test, now), payload))

        upcoming.sort(key=lambda item: item[0])
        return [payload for _, payload in upcoming]

    def list_student_graded_results(
        self,
        *,
        workspace_id: int,
        actor_membership,
        actor_user_id: int,
    ) -> list[dict]:
        attempts = self.attempts.list_graded_for_student(
            workspace_id=workspace_id,
            student_membership_id=actor_membership.id,
            student_user_id=actor_user_id,
        )
        return [
            self._serialize_student_graded_result(attempt)
            for attempt in attempts
            if attempt.test is not None
        ]

    def list_recent_exams(
        self,
        *,
        workspace_id: int,
        actor_membership,
        actor_user_id: int,
        page: int | None = None,
        per_page: int | None = None,
    ) -> dict:
        """Recent submitted/graded attempts for the student dashboard table."""
        page, per_page, offset = normalize_pagination(page, per_page)
        attempts, total = self.attempts.list_recent_for_student(
            workspace_id=workspace_id,
            student_membership_id=actor_membership.id,
            student_user_id=actor_user_id,
            offset=offset,
            limit=per_page,
        )
        items = [
            self._serialize_recent_exam(attempt)
            for attempt in attempts
            if attempt.test is not None
        ]
        return {
            "items": items,
            **build_pagination_meta(total=total, page=page, per_page=per_page),
        }

    def list_student_exams(
        self,
        *,
        workspace_id: int,
        actor_membership,
        actor_user_id: int,
        page: int | None = None,
        per_page: int | None = None,
        lifecycle_status: str | None = None,
    ) -> dict:
        """
        Unified student exam hub — all assigned tests and attempts across lifecycle
        states: UPCOMING, IN_PROGRESS, PENDING_GRADING, GRADED.
        """
        page, per_page, offset = normalize_pagination(page, per_page)

        attempts = self.attempts.list_all_for_student_workspace(
            workspace_id=workspace_id,
            student_membership_id=actor_membership.id,
            student_user_id=actor_user_id,
        )
        for attempt in attempts:
            if attempt.status != TestAttemptStatus.IN_PROGRESS.value:
                continue
            test = attempt.test
            if test is None:
                continue
            self._check_and_apply_timeout(attempt, test)
        db.session.commit()

        items: list[dict] = []
        for attempt in attempts:
            if attempt.test is None:
                continue
            item = self._serialize_student_exam_attempt(attempt)
            if lifecycle_status and item["lifecycle_status"] != lifecycle_status:
                continue
            items.append(item)

        upcoming = self.list_upcoming_tests(
            workspace_id=workspace_id,
            actor_membership=actor_membership,
        )
        now = local_timezone_now()
        for upcoming_item in upcoming:
            if lifecycle_status and lifecycle_status != _LIFECYCLE_UPCOMING:
                continue
            test = self.tests.get_by_id(upcoming_item["test_id"])
            if test is None:
                continue
            items.append(
                self._serialize_student_exam_upcoming(test, upcoming_item, now)
            )

        items.sort(key=self._student_exam_sort_key)
        total = len(items)
        page_items = items[offset : offset + per_page]
        return {
            "items": page_items,
            **build_pagination_meta(total=total, page=page, per_page=per_page),
        }

    def get_exam_entry(
        self,
        *,
        test_id: int,
        workspace_id: int,
        actor_membership,
    ) -> dict:
        """
        Read-only Exam Entry Screen payload.

        Does not create/resume attempts, start timers, or start proctoring.
        """
        test, _ = self._resolve_student_test_access(
            test_id, workspace_id, actor_membership
        )
        self._ensure_exam_available_for_entry(test)

        student_state = self._build_exam_entry_student_state(test, actor_membership)
        settings = self._student_facing_exam_settings(test)
        questions_count = self.test_questions.count_active_for_test(test.id)

        return {
            "exam": self._serialize_exam_entry_exam(test),
            "time": self._serialize_exam_entry_time(test),
            "summary": {
                "questions_count": questions_count,
                "total_score": float(test.total_score)
                if test.total_score is not None
                else self.grading.maximum_score(test),
                "passing_score": float(test.passing_score)
                if test.passing_score is not None
                else None,
            },
            "rules": settings["rules"],
            "instructions": self._build_exam_entry_instructions(settings["rules"]),
            "student": student_state,
        }

    def start_or_resume_attempt(
        self,
        *,
        test_id: int,
        workspace_id: int,
        actor_membership,
        actor_user_id: int,
        student_name: str | None = None,
    ) -> dict:
        test, _ = self._resolve_student_test_access(test_id, workspace_id, actor_membership)
        existing = self.attempts.find_active_for_student(test.id, actor_membership.id)
        if existing:
            # Finalize expired/closed attempts before deciding resume vs new attempt.
            self._check_and_apply_timeout(existing, test)
            if existing.status == TestAttemptStatus.IN_PROGRESS.value:
                self._ensure_resume_allowed(existing, test)
                existing.last_activity_at = local_timezone_now()
                db.session.commit()
                self._notify_teacher_monitoring(test=test, attempt=existing)
                deadline = self._attempt_end_deadline(existing, test)
                if deadline:
                    remaining_minutes = max(
                        0.0, (deadline - local_timezone_now()).total_seconds() / 60
                    )
                    if self._is_survey(test):
                        logger.info(
                            "[SURVEY] Attempt resumed attempt_id=%s closed_at=%s "
                            "remaining_minutes=%.1f",
                            existing.id,
                            deadline.isoformat(),
                            remaining_minutes,
                        )
                    elif self._is_flexible(test):
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
                return self._build_start_or_resume_response(
                    message=Messages.ATTEMPT_RESUMED,
                    attempt=existing,
                    test=test,
                    resumed=True,
                    student_name=student_name,
                )

        # Allow/deny a new attempt by counting completed attempts only.
        # Do not use find_completed_for_student() here: multiple SUBMITTED/GRADED
        # rows are valid when max_attempts > 1 and would crash scalar_one_or_none().
        completed_count = self.attempts.count_completed_for_student(
            test.id, actor_membership.id
        )
        max_attempts = self._max_attempts(test)
        if completed_count >= max_attempts:
            raise ConflictError(
                Messages.YOU_HAVE_REACHED_THE_MAXIMUM_ALLOWED_ATTEMPTS_MAX_ATTEMPTS.format(
                    max_attempts=max_attempts
                )
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
        if self._is_survey(test):
            logger.info(
                "[SURVEY] Attempt started attempt_id=%s test_id=%s closed_at=%s",
                attempt.id,
                test.id,
                expires_at.isoformat() if expires_at else None,
            )
        elif self._is_flexible(test):
            logger.info(
                "[FLEXIBLE] Attempt started attempt_id=%s test_id=%s student_membership_id=%s "
                "ends_at=%s duration_minutes=%s",
                attempt.id,
                test.id,
                actor_membership.id,
                expires_at.isoformat() if expires_at else None,
                test.duration_minutes,
            )
        else:
            logger.info(
                "[SCHEDULED] Attempt started attempt_id=%s test_id=%s global_end=%s",
                attempt.id,
                test.id,
                expires_at.isoformat() if expires_at else None,
            )
        self._maybe_start_proctoring(
            attempt=attempt,
            test=test,
            workspace_id=workspace_id,
        )
        self._notify_teacher_monitoring(test=test, attempt=attempt)
        logger.info(
            "event=attempt_created attempt_id=%s test_id=%s student_membership_id=%s result=success",
            attempt.id,
            test.id,
            actor_membership.id,
        )
        return self._build_start_or_resume_response(
            message=Messages.ATTEMPT_STARTED,
            attempt=attempt,
            test=test,
            resumed=False,
            student_name=student_name,
        )

    def get_current_attempt(
        self, *, test_id: int, workspace_id: int, actor_membership
    ) -> dict:
        test, _ = self._resolve_student_test_access(
            test_id, workspace_id, actor_membership
        )
        attempt = self.attempts.find_active_for_student(test.id, actor_membership.id)
        if not attempt:
            raise NotFoundError(Messages.NO_IN_PROGRESS_ATTEMPT_FOR_THIS_TEST)
        self._check_and_apply_timeout(attempt, test)
        if attempt.status != TestAttemptStatus.IN_PROGRESS.value:
            raise NotFoundError(Messages.NO_IN_PROGRESS_ATTEMPT_FOR_THIS_TEST)
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
        is_own_attempt = attempt.student_membership_id == actor_membership.id

        # Review flag gates educational content only; scores stay visible.
        # include_answers=False skips loading/serializing questions and answers.
        if (
            is_own_attempt
            and attempt.status == TestAttemptStatus.GRADED.value
            and not self._allow_student_review_after_grading(test, attempt)
        ):
            return {
                "attempt": self.serialize_attempt(attempt, include_answers=False),
                "review_allowed": False,
            }

        allow_full_review = (
            is_own_attempt and self._allow_student_review_after_grading(test, attempt)
        )
        # During exam taking (non-GRADED), hide correct-answer flags on choices.
        strip_correctness = student_view or (is_own_attempt and not allow_full_review)
        return {
            "attempt": self.serialize_attempt(
                attempt,
                include_answers=True,
                student_view=strip_correctness,
            ),
            "review_allowed": allow_full_review
            if attempt.status == TestAttemptStatus.GRADED.value
            else None,
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
            "message": Messages.ANSWERS_SAVED,
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
            raise NotFoundError(Messages.TEST_QUESTION_NOT_FOUND_IN_THIS_EXAM)
        logger.info(
            "Updated answer for attempt id=%s test_question_id=%s",
            attempt.id,
            test_question_id,
        )
        return {
            "message": Messages.ANSWER_UPDATED,
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
                raise ForbiddenError(Messages.YOU_CAN_ONLY_SUBMIT_YOUR_OWN_ATTEMPT)
            self._resolve_student_test_access(test_id, workspace_id, actor_membership)

        self._check_and_apply_timeout(attempt, test)
        if attempt.status != TestAttemptStatus.IN_PROGRESS.value:
            raise ConflictError(Messages.ATTEMPT_IS_NOT_IN_PROGRESS)
        self._validate_submission_answer_rules(attempt, test)

        result = self._finalize_attempt(
            attempt, test, submission_source=submission_source
        )
        return {
            "message": Messages.ATTEMPT_SUBMITTED,
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
            raise ValidationError(Messages.MANUAL_GRADING_IS_ONLY_AVAILABLE_WHILE_THE_ATTEMPT_IS_AWAITING_REVIEW)

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
                raise ForbiddenError(Messages.INSUFFICIENT_PERMISSIONS_TO_VIEW_THIS_ATTEMPTS_GRADING_RESULT)
        if attempt.status == TestAttemptStatus.IN_PROGRESS.value:
            raise ValidationError(Messages.GRADING_RESULTS_ARE_AVAILABLE_ONLY_AFTER_SUBMISSION)
        return self.grading.build_grading_result(attempt, test)

    def get_proctoring_grading_review(
        self,
        *,
        test_id: int,
        attempt_id: int,
        workspace_id: int,
        actor_membership,
    ) -> dict:
        attempt = self._get_attempt_or_404(attempt_id, test_id)
        test = self._get_test_in_workspace(test_id, workspace_id)
        self._ensure_teacher_attempt_access(test, workspace_id, actor_membership)
        return self.grading.build_proctoring_grading_review(attempt, test)

    def approve_final_score(
        self,
        *,
        test_id: int,
        attempt_id: int,
        workspace_id: int,
        actor_membership,
        approved: bool,
        final_score: float | None = None,
        reason: str | None = None,
    ) -> dict:
        attempt = self._get_attempt_or_404(attempt_id, test_id)
        test = self._get_test_in_workspace(test_id, workspace_id)
        self._ensure_teacher_attempt_access(test, workspace_id, actor_membership)
        result = self.grading.approve_final_score(
            attempt,
            test,
            approved=approved,
            final_score=final_score,
            reason=reason,
            actor_membership_id=actor_membership.id,
            actor_user_id=actor_membership.user_id,
        )
        became_graded_first_time = bool(result.pop("became_graded_first_time", False))
        self.grading.maybe_send_grading_notification(
            attempt,
            test,
            became_graded_first_time=became_graded_first_time,
        )
        db.session.commit()
        return result

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
        rows = self.attempts.list_in_progress_for_timeout()
        for attempt in rows:
            test = attempt.test or self.tests.get_by_id(attempt.test_id)
            if not test:
                continue
            if not self._should_finalize_attempt(attempt, test, now):
                continue
            # Auto-close surveys whose closed_at has passed.
            if (
                self._is_survey(test)
                and test.status == TestStatus.PUBLISHED.value
                and test.closed_at
                and now >= ensure_local_aware(test.closed_at)
            ):
                test.status = TestStatus.CLOSED.value
            mode_label = self._availability_mode(test)
            logger.info(
                "[%s] Auto-submit attempt_id=%s test_id=%s",
                mode_label,
                attempt.id,
                test.id,
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

    def finalize_in_progress_for_test(self, test: Test) -> list[int]:
        """
        Force-finalize all IN_PROGRESS attempts for a test.

        Not used by teacher/manual or scheduled Test close (close = block new entry only).
        Kept for explicit maintenance / emergency batch finalization callers.
        """
        finalized: list[int] = []
        rows = self.attempts.list_in_progress_for_test(test.id)
        for attempt in rows:
            if attempt.status != TestAttemptStatus.IN_PROGRESS.value:
                continue
            self._finalize_attempt(
                attempt,
                test,
                submission_source=AttemptSubmissionSource.TIMEOUT.value,
            )
            finalized.append(attempt.id)
        return finalized

    def _finalize_attempt(
        self,
        attempt: TestAttempt,
        test: Test,
        *,
        submission_source: str,
        termination_reason: str | None = None,
        proctoring_completed: bool = True,
    ) -> dict:
        if attempt.status != TestAttemptStatus.IN_PROGRESS.value:
            raise ConflictError(Messages.ATTEMPT_IS_ALREADY_FINALIZED)

        now = datetime.now(timezone.utc)
        attempt.status = TestAttemptStatus.SUBMITTED.value
        attempt.submitted_at = now
        attempt.last_activity_at = now
        attempt.submission_source = submission_source
        if termination_reason is not None:
            attempt.termination_reason = termination_reason
        elif submission_source != AttemptSubmissionSource.PROCTORING_AUTO.value:
            # Keep null for normal student/timeout/force unless explicitly set.
            pass

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

        self._maybe_terminate_proctoring(
            attempt=attempt, completed=proctoring_completed
        )

        db.session.commit()
        self._notify_teacher_monitoring(test=test, attempt=attempt)
        logger.info(
            "Finalized attempt id=%s source=%s reason=%s status=%s raw_score=%s",
            attempt.id,
            submission_source,
            attempt.termination_reason,
            attempt.status,
            attempt.raw_score,
        )
        return {
            "attempt": self.serialize_attempt(attempt, include_answers=True),
        }

    def finalize_for_proctoring_auto(
        self,
        *,
        attempt_id: int,
        termination_reason: str | None = None,
    ) -> dict | None:
        """
        Backend-authoritative auto-termination after proctoring escalation.

        Uses row lock + IN_PROGRESS check to avoid double finalization.
        Returns None if the attempt is no longer in progress.
        """
        reason = (
            termination_reason
            or AttemptTerminationReason.PROCTORING_THRESHOLD_EXCEEDED.value
        )
        attempt = db.session.execute(
            db.select(TestAttempt)
            .where(TestAttempt.id == attempt_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not attempt:
            return None
        if attempt.status != TestAttemptStatus.IN_PROGRESS.value:
            return None

        test = attempt.test or self.tests.get_by_id(attempt.test_id)
        if not test:
            return None

        return self._finalize_attempt(
            attempt,
            test,
            submission_source=AttemptSubmissionSource.PROCTORING_AUTO.value,
            termination_reason=reason,
            # Automatic proctoring end → session TERMINATED (not normal COMPLETED).
            proctoring_completed=False,
        )

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
                raise NotFoundError(Messages.TEST_QUESTION_TEST_QUESTION_ID_NOT_FOUND_IN_THIS_EXAM.format(test_question_id=test_question_id))

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
                raise ValidationError(Messages.SELECTED_CHOICE_INDICES_MUST_BE_AN_ARRAY_OF_INTEGERS)

        if type_code in _OBJECTIVE_TYPES and not answer.get_selected_indices():
            if answer.answer_text:
                raise ValidationError(Messages.TYPE_CODE_QUESTIONS_REQUIRE_SELECTED_CHOICE_INDICES.format(type_code=type_code))

        if type_code == "ESSAY" and answer.get_selected_indices():
            raise ValidationError(Messages.ESSAY_QUESTIONS_CANNOT_INCLUDE_SELECTED_CHOICE_INDICES)

    def _check_and_apply_timeout(self, attempt: TestAttempt, test: Test) -> None:
        if attempt.status != TestAttemptStatus.IN_PROGRESS.value:
            return
        now = local_timezone_now()
        if not self._should_finalize_attempt(attempt, test, now):
            return
        mode_label = self._availability_mode(test)
        logger.info(
            "[%s] Timeout/close reached attempt_id=%s test_id=%s",
            mode_label,
            attempt.id,
            attempt.test_id,
        )
        self._finalize_attempt(
            attempt,
            test,
            submission_source=AttemptSubmissionSource.TIMEOUT.value,
        )

    def _should_finalize_attempt(
        self, attempt: TestAttempt, test: Test, now: datetime
    ) -> bool:
        if self._is_test_hard_closed(test, now):
            return True
        deadline = self._attempt_end_deadline(attempt, test)
        return bool(deadline and now >= deadline)

    def _is_test_hard_closed(self, test: Test, now: datetime | None = None) -> bool:
        """
        True only when the exam must stop all attempt activity (including in-progress).

        Teacher/manual CLOSED is NOT hard-close: it blocks new starts only.
        Natural attempt end uses _attempt_end_deadline (duration / global end / survey closed_at).
        """
        if test.status == TestStatus.ARCHIVED.value or test.archived_at is not None:
            return True
        return False

    def _availability_mode(self, test: Test) -> str:
        return (
            test.availability_time_mode or AvailabilityTimeMode.SCHEDULED.value
        ).upper()

    def _is_survey(self, test: Test) -> bool:
        return self._availability_mode(test) == AvailabilityTimeMode.SURVEY.value

    def _is_flexible(self, test: Test) -> bool:
        return self._availability_mode(test) == AvailabilityTimeMode.FLEXIBLE.value

    def _is_scheduled(self, test: Test) -> bool:
        return self._availability_mode(test) == AvailabilityTimeMode.SCHEDULED.value

    def _scheduled_global_end_time(self, test: Test) -> datetime | None:
        if not test.starts_at or not test.duration_minutes:
            return None
        return ensure_local_aware(test.starts_at) + timedelta(
            minutes=int(test.duration_minutes)
        )

    def _attempt_end_deadline(
        self, attempt: TestAttempt, test: Test
    ) -> datetime | None:
        if self._is_survey(test):
            if not test.closed_at:
                return None
            return ensure_local_aware(test.closed_at)
        if self._is_flexible(test):
            # Per-attempt timer only. Teacher close must not cut running flexible attempts.
            if not attempt.expires_at:
                return None
            return ensure_local_aware(attempt.expires_at)
        return self._scheduled_global_end_time(test)

    def _compute_attempt_expires_at(
        self, test: Test, started_at: datetime
    ) -> datetime | None:
        if self._is_survey(test):
            if not test.closed_at:
                raise ValidationError(Messages.SURVEY_CLOSED_AT_IS_REQUIRED)
            return ensure_local_aware(test.closed_at)
        if not test.duration_minutes:
            raise ValidationError(Messages.TEST_DURATION_IS_NOT_CONFIGURED)
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
            raise ValidationError(Messages.TEST_STARTS_AT_AND_DURATION_MINUTES_ARE_REQUIRED_FOR_SCHEDULED_EXAMS)
        logger.info("[SCHEDULED] Global end %s", global_end.isoformat())
        return global_end

    def _ensure_test_takeable_for_first_attempt(self, test: Test) -> None:
        if test.status != TestStatus.PUBLISHED.value:
            raise ValidationError(Messages.TEST_IS_NOT_PUBLISHED)
        now = local_timezone_now()
        if self._is_test_hard_closed(test, now):
            raise ForbiddenError(Messages.EXAM_HAS_ALREADY_ENDED)

        if self._is_survey(test):
            if not test.closed_at:
                raise ValidationError(Messages.SURVEY_CLOSED_AT_IS_REQUIRED)
            if now >= ensure_local_aware(test.closed_at):
                raise ForbiddenError(Messages.EXAM_HAS_ALREADY_ENDED)
            logger.info("[SURVEY] Exam available for first attempt test_id=%s", test.id)
            return

        if not test.duration_minutes:
            raise ValidationError(Messages.TEST_DURATION_IS_NOT_CONFIGURED)

        if self._is_flexible(test):
            logger.info(
                "[FLEXIBLE] Exam available for first attempt test_id=%s",
                test.id,
            )
            return

        if not test.starts_at:
            raise ValidationError(Messages.TEST_START_TIME_IS_NOT_CONFIGURED)
        starts_at = ensure_local_aware(test.starts_at)
        if now < starts_at:
            raise ValidationError(Messages.TEST_HAS_NOT_STARTED_YET)
        global_end = self._scheduled_global_end_time(test)
        if global_end and now >= global_end:
            raise ForbiddenError(Messages.EXAM_HAS_ALREADY_ENDED)
        if test.entry_window_minutes:
            window_end = starts_at + timedelta(
                minutes=int(test.entry_window_minutes)
            )
            if now > window_end:
                logger.info(
                    "event=entry_window_rejected test_id=%s reason=window_closed result=forbidden",
                    test.id,
                )
                raise ForbiddenError(Messages.ENTRY_WINDOW_HAS_CLOSED)
        logger.info(
            "[SCHEDULED] Global end %s",
            global_end.isoformat() if global_end else "n/a",
        )

    def _ensure_resume_allowed(self, attempt: TestAttempt, test: Test) -> None:
        if attempt.status != TestAttemptStatus.IN_PROGRESS.value:
            raise ConflictError(Messages.ATTEMPT_IS_NOT_IN_PROGRESS)
        # CLOSED still allows resume of an already-running attempt; ARCHIVED does not.
        if self._is_test_hard_closed(test):
            raise ForbiddenError(Messages.EXAM_IS_NO_LONGER_AVAILABLE_FOR_RESUME)
        if test.status not in (
            TestStatus.PUBLISHED.value,
            TestStatus.CLOSED.value,
        ):
            raise ForbiddenError(Messages.EXAM_IS_NO_LONGER_AVAILABLE_FOR_RESUME)
        deadline = self._attempt_end_deadline(attempt, test)
        if deadline and local_timezone_now() >= deadline:
            raise ForbiddenError(Messages.EXAM_HAS_ALREADY_ENDED)

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

        student_name = self._student_display_name(attempt)
        payload = {
            "id": attempt.id,
            "test_id": attempt.test_id,
            "student_membership_id": attempt.student_membership_id,
            "user_id": attempt.user_id,
            "student_name": student_name,
            "user_name": student_name,
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
            "termination_reason": attempt.termination_reason,
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
            "snapshot_image_path": row.snapshot_image_path,
            "snapshot_image_url": self._build_image_url(row.snapshot_image_path),
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

    @staticmethod
    def _student_display_name(attempt: TestAttempt) -> str | None:
        user = attempt.user
        if user is not None and user.full_name:
            return user.full_name
        membership = attempt.student_membership
        if membership is not None and membership.user is not None:
            return membership.user.full_name
        return None

    def _build_start_or_resume_response(
        self,
        *,
        message: str,
        attempt: TestAttempt,
        test: Test,
        resumed: bool,
        student_name: str | None,
    ) -> dict:
        resolved_user_name = student_name or self._student_display_name(attempt)

        teacher_name = None
        if test.created_by and test.created_by.user:
            teacher_name = test.created_by.user.full_name

        attempt_payload = self.serialize_attempt(attempt, include_answers=True)
        attempt_payload["student_name"] = resolved_user_name
        attempt_payload["user_name"] = resolved_user_name

        return {
            "message": message,
            "resumed": resumed,
            "attempt": attempt_payload,
            "exam": {
                "name": test.name,
                "description": test.description,
                "subject_name": test.subject.name if test.subject else None,
                "teacher_name": teacher_name,
            },
            "student_name": resolved_user_name,
            "user_name": resolved_user_name,
            "teacher_name": teacher_name,
        }

    def _serialize_test_summary(self, test: Test) -> dict:
        teacher_name = None
        if test.created_by and test.created_by.user:
            teacher_name = test.created_by.user.full_name
        return {
            "test_id": test.id,
            "name": test.name,
            "slug": test.slug,
            "description": test.description,
            "subject_id": test.subject_id,
            "status": test.status,
            "availability_time_mode": test.availability_time_mode,
            "duration_minutes": test.duration_minutes,
            "starts_at": format_local_datetime(test.starts_at),
            "closed_at": format_local_datetime(test.closed_at),
            "published_at": format_local_datetime(test.published_at),
            "total_score": float(test.total_score) if test.total_score is not None else None,
            "passing_score": float(test.passing_score)
            if test.passing_score is not None
            else None,
            "teacher_name": teacher_name,
        }

    def _serialize_upcoming_test(self, test: Test, now: datetime) -> dict:
        mode = self._availability_mode(test)
        teacher_name = None
        if test.created_by and test.created_by.user:
            teacher_name = test.created_by.user.full_name

        payload: dict = {
            "test_id": test.id,
            "title": test.name,
            "subject": test.subject.name if test.subject else None,
            "teacher_name": teacher_name,
            "status": test.status,
            "availability_time_mode": mode,
        }

        if self._is_survey(test) or self._is_flexible(test):
            payload["start_time"] = None
            payload["starts_on_entry"] = True
            payload["duration_minutes"] = (
                None if self._is_survey(test) else test.duration_minutes
            )
            payload["availability_note"] = (
                "Open until closed_at" if self._is_survey(test) else "Starts on entry"
            )
            payload["end_time"] = format_local_datetime(test.closed_at)
            window: dict = {}
            if test.published_at:
                window["available_from"] = format_local_datetime(test.published_at)
            if test.closed_at:
                window["available_until"] = format_local_datetime(test.closed_at)
            if window:
                payload["availability_window"] = window
            return payload

        start = ensure_local_aware(test.starts_at) if test.starts_at else None
        global_end = self._scheduled_global_end_time(test)
        payload["start_time"] = format_local_datetime(test.starts_at)
        payload["end_time"] = format_local_datetime(global_end)
        payload["duration_minutes"] = test.duration_minutes

        if start:
            seconds_until = int((start - now).total_seconds())
            if seconds_until > 0:
                payload["time_until_start_seconds"] = seconds_until
                payload["time_until_start_human"] = self._format_countdown(seconds_until)
            else:
                payload["time_until_start_seconds"] = 0
                payload["time_until_start_human"] = "Available now"
        else:
            payload["time_until_start_seconds"] = None
            payload["time_until_start_human"] = None

        return payload

    def _serialize_student_graded_result(self, attempt: TestAttempt) -> dict:
        test = attempt.test
        max_score = self.grading.maximum_score(test)
        teacher_name = None
        if test.created_by and test.created_by.user:
            teacher_name = test.created_by.user.full_name

        score = attempt.final_score
        if score is not None:
            score = float(score)
        percentage = attempt.percentage
        if percentage is not None:
            percentage = float(percentage)

        return {
            "test_id": test.id,
            "attempt_id": attempt.id,
            "student_name": self._student_display_name(attempt),
            "title": test.name,
            "subject": test.subject.name if test.subject else None,
            "teacher_name": teacher_name,
            "score": score,
            "max_score": max_score,
            "percentage": percentage,
            "status": attempt.status,
            "graded_at": format_local_datetime(attempt.graded_at),
        }

    def _serialize_recent_exam(self, attempt: TestAttempt) -> dict:
        test = attempt.test
        subject = test.subject if test else None
        grading_completed = attempt.status == TestAttemptStatus.GRADED.value
        ui_status = (
            _RECENT_STATUS_GRADED
            if grading_completed
            else _RECENT_STATUS_PENDING_GRADING
        )

        teacher_name = None
        if test.created_by and test.created_by.user:
            teacher_name = test.created_by.user.full_name

        score = None
        if grading_completed and attempt.final_score is not None:
            percentage = (
                float(attempt.percentage) if attempt.percentage is not None else None
            )
            score = {
                "earned": float(attempt.final_score),
                "maximum": self.grading.maximum_score(test),
                "percentage": percentage,
            }

        return {
            "attempt_id": attempt.id,
            "student_name": self._student_display_name(attempt),
            "status": ui_status,
            "submitted_at": attempt.submitted_at.isoformat()
            if attempt.submitted_at
            else None,
            "subject": {
                "id": subject.id,
                "name": subject.name,
            }
            if subject
            else None,
            "teacher_name": teacher_name,
            "test": {
                "id": test.id,
                "title": test.name,
                "published_at": test.published_at.isoformat()
                if test.published_at
                else None,
            },
            "score": score,
            "review_allowed": self._allow_student_review_after_grading(test, attempt)
            if grading_completed
            else False,
        }

    def _attempt_lifecycle_status(self, attempt: TestAttempt) -> str:
        if attempt.status == TestAttemptStatus.IN_PROGRESS.value:
            return _LIFECYCLE_IN_PROGRESS
        if attempt.status == TestAttemptStatus.SUBMITTED.value:
            return _LIFECYCLE_PENDING_GRADING
        if attempt.status == TestAttemptStatus.GRADED.value:
            return _LIFECYCLE_GRADED
        return attempt.status

    def _serialize_student_exam_attempt(self, attempt: TestAttempt) -> dict:
        test = attempt.test
        subject = test.subject if test else None
        lifecycle_status = self._attempt_lifecycle_status(attempt)
        teacher_name = None
        if test.created_by and test.created_by.user:
            teacher_name = test.created_by.user.full_name

        score = None
        if lifecycle_status == _LIFECYCLE_GRADED and attempt.final_score is not None:
            percentage = (
                float(attempt.percentage) if attempt.percentage is not None else None
            )
            score = {
                "earned": float(attempt.final_score),
                "maximum": self.grading.maximum_score(test),
                "percentage": percentage,
            }

        can_resume = False
        if lifecycle_status == _LIFECYCLE_IN_PROGRESS:
            can_resume = self._can_resume_attempt(attempt, test)

        return {
            "test_id": test.id,
            "attempt_id": attempt.id,
            "student_name": self._student_display_name(attempt),
            "title": test.name,
            "subject": {
                "id": subject.id,
                "name": subject.name,
            }
            if subject
            else None,
            "teacher_name": teacher_name,
            "lifecycle_status": lifecycle_status,
            "attempt_status": attempt.status,
            "submission_source": attempt.submission_source,
            "termination_reason": attempt.termination_reason,
            "started_at": format_local_datetime(attempt.started_at),
            "submitted_at": format_local_datetime(attempt.submitted_at),
            "graded_at": format_local_datetime(attempt.graded_at),
            "last_activity_at": format_local_datetime(attempt.last_activity_at),
            "score": score,
            "review_allowed": self._allow_student_review_after_grading(test, attempt)
            if lifecycle_status == _LIFECYCLE_GRADED
            else False,
            "can_resume": can_resume,
            "resume_attempt_id": attempt.id if can_resume else None,
        }

    def _serialize_student_exam_upcoming(
        self, test: Test, upcoming_item: dict, now: datetime
    ) -> dict:
        return {
            "test_id": test.id,
            "attempt_id": None,
            "title": upcoming_item.get("title") or test.name,
            "subject": {
                "name": upcoming_item.get("subject"),
            }
            if upcoming_item.get("subject")
            else None,
            "teacher_name": upcoming_item.get("teacher_name"),
            "lifecycle_status": _LIFECYCLE_UPCOMING,
            "attempt_status": None,
            "submission_source": None,
            "started_at": None,
            "submitted_at": None,
            "graded_at": None,
            "last_activity_at": None,
            "score": None,
            "review_allowed": False,
            "can_resume": False,
            "resume_attempt_id": None,
            "availability_time_mode": upcoming_item.get("availability_time_mode"),
            "start_time": upcoming_item.get("start_time"),
            "end_time": upcoming_item.get("end_time"),
            "duration_minutes": upcoming_item.get("duration_minutes"),
            "starts_on_entry": upcoming_item.get("starts_on_entry"),
            "availability_note": upcoming_item.get("availability_note"),
            "time_until_start_seconds": upcoming_item.get("time_until_start_seconds"),
            "time_until_start_human": upcoming_item.get("time_until_start_human"),
        }

    def _student_exam_sort_key(self, item: dict) -> tuple:
        lifecycle = item.get("lifecycle_status") or ""
        order = _LIFECYCLE_SORT_ORDER.get(lifecycle, 99)
        activity_field = {
            _LIFECYCLE_IN_PROGRESS: "last_activity_at",
            _LIFECYCLE_PENDING_GRADING: "submitted_at",
            _LIFECYCLE_GRADED: "graded_at",
            _LIFECYCLE_UPCOMING: "start_time",
        }.get(lifecycle, "started_at")
        activity = item.get(activity_field) or item.get("started_at") or ""
        ts = 0.0
        if activity:
            try:
                ts = ensure_local_aware(
                    datetime.fromisoformat(str(activity).replace("Z", ""))
                ).timestamp()
            except ValueError:
                ts = 0.0
        return (order, -ts, -(item.get("test_id") or 0))

    def _is_upcoming_window_closed(self, test: Test, now: datetime) -> bool:
        if self._is_test_hard_closed(test, now):
            return True
        if self._is_survey(test):
            if test.closed_at and now >= ensure_local_aware(test.closed_at):
                return True
            return False
        if self._is_flexible(test):
            return False

        global_end = self._scheduled_global_end_time(test)
        if global_end and now >= global_end:
            return True
        return False

    def _upcoming_sort_key(self, test: Test, now: datetime) -> tuple:
        if self._is_survey(test) or self._is_flexible(test):
            published = ensure_local_aware(test.published_at) if test.published_at else now
            return (2, published, test.id)

        if not test.starts_at:
            return (1, now, test.id)

        start = ensure_local_aware(test.starts_at)
        tier = 0 if start > now else 1
        return (tier, start, test.id)

    @staticmethod
    def _format_countdown(total_seconds: int) -> str:
        if total_seconds <= 0:
            return "Available now"

        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)

        if days > 0:
            label = "day" if days == 1 else "days"
            return f"{days} {label} left"
        if hours > 0 and minutes > 0:
            return f"{hours}h {minutes}m left"
        if hours > 0:
            return f"{hours}h left"
        if minutes > 0:
            return f"{minutes}m left"
        return f"{total_seconds}s left"

    def _max_attempts(self, test: Test) -> int:
        settings = self._load_json(test.settings_config) or {}
        attempt_settings = settings.get("attempt_settings") or {}
        raw = attempt_settings.get("max_attempts")
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = 1
        return max(1, value)

    def _ensure_exam_available_for_entry(self, test: Test) -> None:
        if test.status != TestStatus.PUBLISHED.value or test.archived_at is not None:
            raise ValidationError(Messages.TEST_IS_NOT_PUBLISHED)
        if self._is_test_hard_closed(test):
            raise ForbiddenError(Messages.EXAM_HAS_ALREADY_ENDED)
        if self._is_survey(test):
            return
        if not test.duration_minutes:
            raise ValidationError(Messages.TEST_DURATION_IS_NOT_CONFIGURED)

    def _student_facing_exam_settings(self, test: Test) -> dict:
        settings = self._load_json(test.settings_config) or {}
        navigation = settings.get("navigation_settings") or {}
        answer_rules = settings.get("answer_rules") or {}
        display = settings.get("display_settings") or {}
        proctoring = settings.get("proctoring") or {}
        offline = settings.get("offline_policy") or {}
        proctoring_enabled = bool(proctoring.get("enabled", False))
        grace = offline.get("grace_period_minutes")
        if "grace_period_minutes" not in offline:
            from service.test_service import TestService

            grace = TestService._resolve_offline_grace_minutes(
                mode=self._availability_mode(test),
                proctoring_enabled=proctoring_enabled,
                offline_raw={},
            )
        rules = {
            "allow_back_navigation": bool(navigation.get("allow_back_navigation", True)),
            "allow_skip_questions": bool(answer_rules.get("allow_skip_questions", True)),
            "require_answer_all": bool(answer_rules.get("require_answer_all", False)),
            "shuffle_questions": bool(display.get("shuffle_questions", False)),
            "shuffle_choices": bool(display.get("shuffle_choices", False)),
            "max_attempts": self._max_attempts(test),
            "proctoring_enabled": proctoring_enabled
            if not self._is_survey(test)
            else False,
            "offline_grace_period_minutes": grace,
        }
        if rules["require_answer_all"] and rules["allow_skip_questions"]:
            rules["allow_skip_questions"] = False
        return {"rules": rules}

    def _serialize_exam_entry_exam(self, test: Test) -> dict:
        subject = test.subject
        teacher_name = None
        if test.created_by and test.created_by.user:
            teacher_name = test.created_by.user.full_name
        return {
            "id": test.id,
            "title": test.name,
            "description": test.description,
            "subject": {
                "id": subject.id,
                "name": subject.name,
            }
            if subject
            else None,
            "teacher": {"name": teacher_name} if teacher_name else {"name": None},
        }

    def _serialize_exam_entry_time(self, test: Test) -> dict:
        mode = self._availability_mode(test)
        payload = {
            "availability_mode": mode,
            "duration_minutes": None if self._is_survey(test) else test.duration_minutes,
            "starts_at": None,
            "ends_at": None,
            "entry_window_minutes": None,
            "closed_at": format_local_datetime(test.closed_at),
        }
        if self._is_survey(test):
            payload["ends_at"] = format_local_datetime(test.closed_at)
            return payload
        if self._is_scheduled(test):
            global_end = self._scheduled_global_end_time(test)
            payload["starts_at"] = (
                ensure_local_aware(test.starts_at).isoformat() if test.starts_at else None
            )
            payload["ends_at"] = global_end.isoformat() if global_end else None
            payload["entry_window_minutes"] = test.entry_window_minutes
        elif self._is_flexible(test):
            payload["ends_at"] = format_local_datetime(test.closed_at)
        return payload

    def _build_exam_entry_instructions(self, rules: dict) -> list[str]:
        instructions = [
            "Ensure that your internet connection is stable.",
            "Do not leave the exam page.",
            "The exam will be submitted automatically when the timer expires.",
        ]
        if rules.get("proctoring_enabled"):
            instructions.insert(1, "Allow camera and microphone access.")
        if not rules.get("allow_back_navigation"):
            instructions.append("You cannot go back to previous questions.")
        if rules.get("require_answer_all"):
            instructions.append("You must answer all questions before submitting.")
        grace = rules.get("offline_grace_period_minutes")
        if grace is not None:
            instructions.append(
                f"If you lose connectivity, you have up to {grace} minutes of offline grace "
                "before the attempt may be finalized. Offline grace never extends the exam deadline."
            )
        return instructions

    def _build_exam_entry_student_state(
        self, test: Test, actor_membership
    ) -> dict:
        active_attempt = self.attempts.find_active_for_student(
            test.id, actor_membership.id
        )
        max_attempts = self._max_attempts(test)
        completed_count = self.attempts.count_completed_for_student(
            test.id, actor_membership.id
        )
        remaining_attempts = max(0, max_attempts - completed_count)

        if active_attempt is not None:
            can_resume = self._can_resume_attempt(active_attempt, test)
            return {
                "remaining_attempts": remaining_attempts,
                "can_start": can_resume,
                "already_started": True,
                "resume_attempt_id": active_attempt.id,
            }

        can_start = remaining_attempts > 0 and self._can_start_first_attempt(test)
        return {
            "remaining_attempts": remaining_attempts,
            "can_start": can_start,
            "already_started": False,
            "resume_attempt_id": None,
        }

    def _can_resume_attempt(self, attempt: TestAttempt, test: Test) -> bool:
        if attempt.status != TestAttemptStatus.IN_PROGRESS.value:
            return False
        if self._is_test_hard_closed(test):
            return False
        if test.status not in (
            TestStatus.PUBLISHED.value,
            TestStatus.CLOSED.value,
        ):
            return False
        deadline = self._attempt_end_deadline(attempt, test)
        if deadline and local_timezone_now() >= deadline:
            return False
        return True

    def _can_start_first_attempt(self, test: Test) -> bool:
        """Mirror _ensure_test_takeable_for_first_attempt without raising."""
        if test.status != TestStatus.PUBLISHED.value:
            return False
        if self._is_test_hard_closed(test):
            return False
        now = local_timezone_now()
        if self._is_survey(test):
            if test.closed_at is None:
                return False
            return now < ensure_local_aware(test.closed_at)
        if not test.duration_minutes:
            return False
        if self._is_flexible(test):
            return True

        if not test.starts_at:
            return False
        starts_at = ensure_local_aware(test.starts_at)
        if now < starts_at:
            return False
        global_end = self._scheduled_global_end_time(test)
        if global_end and now >= global_end:
            return False
        if test.entry_window_minutes:
            entry_deadline = starts_at + timedelta(minutes=int(test.entry_window_minutes))
            if now >= entry_deadline:
                return False
        return True

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
                Messages.ALL_QUESTIONS_MUST_BE_ANSWERED_BEFORE_SUBMISSION_MISSING_ANSWERS_FOR_QUESTION_IDS.format(
                    missing_question_ids=missing_question_ids
                )
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
            raise ForbiddenError(Messages.YOU_CAN_ONLY_MODIFY_YOUR_OWN_ATTEMPT)
        self._resolve_student_test_access(test_id, workspace_id, actor_membership)
        self._check_and_apply_timeout(attempt, test)
        if attempt.status != TestAttemptStatus.IN_PROGRESS.value:
            raise ConflictError(Messages.ATTEMPT_IS_NOT_IN_PROGRESS)
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
            raise ForbiddenError(Messages.YOU_ARE_NOT_ENROLLED_IN_THIS_TESTS_SUBJECT)
        if actor_membership.role == MembershipRole.STUDENT.value:
            if not verify_subject_student_access(actor_link):
                raise ForbiddenError(Messages.ONLY_STUDENTS_ENROLLED_IN_THE_SUBJECT_CAN_TAKE_TESTS)
            assignment = self.test_assignments.find(
                test_id=test.id,
                student_membership_id=actor_membership.id,
            )
            if not assignment:
                raise ForbiddenError(Messages.YOU_ARE_NOT_ASSIGNED_TO_THIS_EXAM)
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
            raise ForbiddenError(Messages.CANNOT_VIEW_ANOTHER_STUDENTS_ATTEMPT_IN_STUDENT_MODE)
        self._ensure_teacher_attempt_access(test, workspace_id, actor_membership)

    def _allow_student_review_after_grading(
        self, test: Test, attempt: TestAttempt
    ) -> bool:
        if attempt.status != TestAttemptStatus.GRADED.value:
            return False
        from utils.review_settings import allow_review_after_grading

        return allow_review_after_grading(test.settings_config)

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
            raise ForbiddenError(Messages.INSUFFICIENT_PERMISSIONS_TO_MANAGE_ATTEMPTS)

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
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)
        return workspace

    def _get_test_in_workspace(self, test_id: int, workspace_id: int) -> Test:
        test = self.tests.get_by_id_in_workspace(test_id, workspace_id)
        if not test:
            raise NotFoundError(Messages.TEST_NOT_FOUND)
        return test

    def _get_attempt_or_404(self, attempt_id: int, test_id: int) -> TestAttempt:
        attempt = self.attempts.get_for_test(attempt_id, test_id)
        if not attempt:
            raise NotFoundError(Messages.ATTEMPT_NOT_FOUND)
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

    def _notify_teacher_monitoring(self, *, test: Test, attempt: TestAttempt) -> None:
        from service.proctoring_service import ProctoringService

        try:
            ProctoringService().notify_monitoring_row_updated(
                test=test,
                attempt=attempt,
            )
        except Exception:
            logger.exception(
                "Failed to notify teacher monitors for attempt id=%s", attempt.id
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

    def _build_image_url(self, image_path: str | None) -> str | None:
        if not image_path:
            return None
        base_url = current_app.config.get("API_URL", "").rstrip("/")
        return f"{base_url}/uploads/{image_path}"
