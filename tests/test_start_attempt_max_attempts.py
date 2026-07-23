"""Unit tests for multi-attempt start gate (no DB)."""

import unittest
from unittest.mock import MagicMock, patch

from service.attempt_service import AttemptService
from service.exceptions import ConflictError
from utils.enums import TestAttemptStatus
from utils.messages import Messages


class StartAttemptMaxAttemptsGateTests(unittest.TestCase):
    def setUp(self):
        self.svc = AttemptService.__new__(AttemptService)
        self.svc.attempts = MagicMock()
        self.svc.tests = MagicMock()
        self.svc.grading = MagicMock()
        self.svc.subjects = MagicMock()
        self.svc.subject_memberships = MagicMock()
        self.svc.test_assignments = MagicMock()
        self.svc.workspaces = MagicMock()

        self.test = MagicMock()
        self.test.id = 42
        self.test.settings_config = {"attempt_settings": {"max_attempts": 3}}
        self.membership = MagicMock()
        self.membership.id = 7

    def test_allows_new_attempt_when_completed_below_max(self):
        self.svc.attempts.find_active_for_student.return_value = None
        self.svc.attempts.count_completed_for_student.return_value = 2
        self.svc._resolve_student_test_access = MagicMock(return_value=(self.test, None))
        self.svc._max_attempts = MagicMock(return_value=3)
        self.svc._ensure_test_takeable_for_first_attempt = MagicMock()
        self.svc._compute_attempt_expires_at = MagicMock(return_value=None)
        self.svc._maybe_start_proctoring = MagicMock()
        self.svc._is_survey = MagicMock(return_value=False)
        self.svc._is_flexible = MagicMock(return_value=False)
        self.svc._build_start_or_resume_response = MagicMock(
            return_value={"resumed": False, "message": "ok"}
        )

        with patch("service.attempt_service.TestAttempt") as AttemptCls, patch(
            "service.attempt_service.db"
        ):
            AttemptCls.return_value = MagicMock(id=99)
            result = self.svc.start_or_resume_attempt(
                test_id=42,
                workspace_id=1,
                actor_membership=self.membership,
                actor_user_id=10,
            )

        self.svc.attempts.find_completed_for_student.assert_not_called()
        self.svc.attempts.count_completed_for_student.assert_called_once_with(42, 7)
        self.svc._ensure_test_takeable_for_first_attempt.assert_called_once()
        self.assertEqual(result["resumed"], False)

    def test_rejects_when_completed_reaches_max(self):
        self.svc.attempts.find_active_for_student.return_value = None
        self.svc.attempts.count_completed_for_student.return_value = 3
        self.svc._resolve_student_test_access = MagicMock(return_value=(self.test, None))
        self.svc._max_attempts = MagicMock(return_value=3)

        with self.assertRaises(ConflictError) as ctx:
            self.svc.start_or_resume_attempt(
                test_id=42,
                workspace_id=1,
                actor_membership=self.membership,
                actor_user_id=10,
            )

        self.assertIn("maximum allowed attempts", ctx.exception.message)
        self.svc.attempts.find_completed_for_student.assert_not_called()

    def test_resumes_in_progress_before_count_gate(self):
        existing = MagicMock()
        existing.status = TestAttemptStatus.IN_PROGRESS.value
        existing.id = 19
        self.svc.attempts.find_active_for_student.return_value = existing
        self.svc._resolve_student_test_access = MagicMock(return_value=(self.test, None))
        self.svc._check_and_apply_timeout = MagicMock()
        self.svc._ensure_resume_allowed = MagicMock()
        self.svc._attempt_end_deadline = MagicMock(return_value=None)
        self.svc._build_start_or_resume_response = MagicMock(
            return_value={"resumed": True, "message": Messages.ATTEMPT_RESUMED}
        )

        with patch("service.attempt_service.db"), patch(
            "service.attempt_service.local_timezone_now"
        ):
            result = self.svc.start_or_resume_attempt(
                test_id=42,
                workspace_id=1,
                actor_membership=self.membership,
                actor_user_id=10,
            )

        self.svc._check_and_apply_timeout.assert_called_once_with(existing, self.test)
        self.svc._ensure_resume_allowed.assert_called_once()
        self.svc.attempts.count_completed_for_student.assert_not_called()
        self.assertTrue(result["resumed"])


if __name__ == "__main__":
    unittest.main()
