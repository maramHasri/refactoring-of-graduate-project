"""Unit checks for Flexible planned closed_at + auto-close.

Run: python tests/test_flexible_auto_close.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_flexible_future_closed_at_not_closed_by_job():
    from service.test_service import TestService
    from utils.enums import TestStatus

    svc = object.__new__(TestService)
    svc.tests = MagicMock()
    now = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    # Repository already filters due rows; empty list means future closed_at not due.
    svc.tests.list_published_flexible_due_for_auto_close.return_value = []

    with patch("service.test_service.local_timezone_now", return_value=now):
        with patch.object(TestService, "_apply_test_close") as apply_close:
            closed_ids = TestService.close_due_flexible_tests(svc)

    assert closed_ids == []
    apply_close.assert_not_called()
    svc.tests.list_published_flexible_due_for_auto_close.assert_called_once_with(now=now)


def test_flexible_past_closed_at_applies_shared_close():
    from service.test_service import TestService
    from utils.enums import AvailabilityTimeMode, TestStatus

    svc = object.__new__(TestService)
    svc.tests = MagicMock()
    now = datetime(2026, 8, 10, 23, 59, tzinfo=timezone.utc)
    due = SimpleNamespace(
        id=51,
        status=TestStatus.PUBLISHED.value,
        availability_time_mode=AvailabilityTimeMode.FLEXIBLE.value,
        closed_at=now - timedelta(minutes=1),
    )
    svc.tests.list_published_flexible_due_for_auto_close.return_value = [due]

    with patch("service.test_service.local_timezone_now", return_value=now):
        with patch.object(
            TestService, "_apply_test_close", return_value=True
        ) as apply_close:
            with patch("service.test_service.db") as mock_db:
                closed_ids = TestService.close_due_flexible_tests(svc)

    assert closed_ids == [51]
    apply_close.assert_called_once_with(due)
    mock_db.session.commit.assert_called_once()


def test_flexible_auto_close_does_not_finalize_attempts():
    from service.test_service import TestService
    from utils.enums import TestStatus

    svc = object.__new__(TestService)
    svc.tests = MagicMock()
    now = datetime(2026, 8, 10, 23, 59, tzinfo=timezone.utc)
    due = SimpleNamespace(
        id=51,
        status=TestStatus.PUBLISHED.value,
        closed_at=now,
    )
    svc.tests.list_published_flexible_due_for_auto_close.return_value = [due]

    with patch("service.test_service.local_timezone_now", return_value=now):
        with patch("service.attempt_service.AttemptService") as AttemptSvc:
            with patch.object(TestService, "_apply_test_close", return_value=True):
                with patch("service.test_service.db"):
                    TestService.close_due_flexible_tests(svc)

    AttemptSvc.assert_not_called()


def test_flexible_start_blocked_after_closed_at():
    from service.exceptions import ForbiddenError
    from service.attempt_service import AttemptService
    from utils.enums import TestStatus

    svc = object.__new__(AttemptService)
    now = datetime(2026, 8, 10, 23, 59, tzinfo=timezone.utc)
    test = SimpleNamespace(
        id=9,
        status=TestStatus.PUBLISHED.value,
        availability_time_mode="FLEXIBLE",
        closed_at=now - timedelta(seconds=1),
        duration_minutes=60,
        archived_at=None,
        starts_at=None,
    )
    svc._is_test_hard_closed = MagicMock(return_value=False)

    with patch("service.attempt_service.local_timezone_now", return_value=now):
        with patch(
            "service.attempt_service.ensure_local_aware", side_effect=lambda dt: dt
        ):
            try:
                AttemptService._ensure_test_takeable_for_first_attempt(svc, test)
                raise AssertionError("expected ForbiddenError")
            except ForbiddenError:
                pass
            assert AttemptService._can_start_first_attempt(svc, test) is False


def test_flexible_resume_still_allowed_when_test_closed():
    from service.attempt_service import AttemptService
    from utils.enums import TestAttemptStatus, TestStatus

    svc = object.__new__(AttemptService)
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    attempt = SimpleNamespace(
        status=TestAttemptStatus.IN_PROGRESS.value,
        expires_at=now + timedelta(minutes=20),
    )
    test = SimpleNamespace(
        status=TestStatus.CLOSED.value,
        archived_at=None,
        availability_time_mode="FLEXIBLE",
        closed_at=now - timedelta(minutes=5),
        starts_at=None,
        duration_minutes=60,
    )
    svc._is_test_hard_closed = MagicMock(return_value=False)

    with patch("service.attempt_service.local_timezone_now", return_value=now):
        with patch(
            "service.attempt_service.ensure_local_aware", side_effect=lambda dt: dt
        ):
            AttemptService._ensure_resume_allowed(svc, attempt, test)


def test_flexible_deadline_still_uses_expires_at_not_closed_at():
    from service.attempt_service import AttemptService

    svc = object.__new__(AttemptService)
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    attempt = SimpleNamespace(expires_at=now + timedelta(minutes=30))
    test = SimpleNamespace(
        availability_time_mode="FLEXIBLE",
        closed_at=now - timedelta(hours=1),
        starts_at=None,
        duration_minutes=60,
    )
    with patch(
        "service.attempt_service.ensure_local_aware", side_effect=lambda dt: dt
    ):
        deadline = AttemptService._attempt_end_deadline(svc, attempt, test)
    assert deadline == attempt.expires_at


def test_scheduled_auto_close_regression_still_uses_global_end():
    from service.test_service import TestService
    from utils.enums import TestStatus

    svc = object.__new__(TestService)
    svc.tests = MagicMock()
    now = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
    ended = SimpleNamespace(
        id=10,
        status=TestStatus.PUBLISHED.value,
        starts_at=now - timedelta(hours=2),
        duration_minutes=60,
    )
    svc.tests.list_published_scheduled_for_auto_close.return_value = [ended]

    with patch("service.test_service.local_timezone_now", return_value=now):
        with patch("service.attempt_service.AttemptService") as AttemptSvc:
            AttemptSvc.return_value._scheduled_global_end_time.side_effect = (
                lambda test: test.starts_at
                + timedelta(minutes=int(test.duration_minutes))
            )
            with patch.object(
                TestService, "_apply_test_close", return_value=True
            ) as apply_close:
                with patch("service.test_service.db"):
                    closed_ids = TestService.close_due_scheduled_tests(svc)

    assert closed_ids == [10]
    apply_close.assert_called_once_with(ended)


def test_survey_closed_at_still_attempt_deadline():
    from service.attempt_service import AttemptService

    svc = object.__new__(AttemptService)
    closed = datetime(2026, 8, 10, 23, 59, tzinfo=timezone.utc)
    attempt = SimpleNamespace(expires_at=None)
    test = SimpleNamespace(
        availability_time_mode="SURVEY",
        closed_at=closed,
        starts_at=None,
        duration_minutes=None,
    )
    with patch(
        "service.attempt_service.ensure_local_aware", side_effect=lambda dt: dt
    ):
        deadline = AttemptService._attempt_end_deadline(svc, attempt, test)
    assert deadline == closed


def test_job_calls_scheduled_and_flexible_close():
    from jobs import scheduled_test_publisher as job

    app = MagicMock()

    with patch("jobs.scheduled_test_publisher.TestService", create=True):
        pass

    with app.app_context():
        pass

    with patch(
        "service.test_service.TestService"
    ) as Svc:
        instance = Svc.return_value
        instance.close_due_scheduled_tests.return_value = [1]
        instance.close_due_flexible_tests.return_value = [2]
        result = job._auto_close_due_tests(app)

    assert result == [1, 2]
    instance.close_due_scheduled_tests.assert_called_once()
    instance.close_due_flexible_tests.assert_called_once()


if __name__ == "__main__":
    tests = [name for name, obj in list(globals().items()) if name.startswith("test_")]
    failed = 0
    for name in tests:
        try:
            globals()[name]()
            print(f"OK  {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
    if failed:
        raise SystemExit(1)
    print(f"\n{len(tests)} passed")
