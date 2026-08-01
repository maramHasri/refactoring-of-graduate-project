"""Unit checks: closed test keeps running attempts alive.

Run: python tests/test_close_keeps_in_progress_attempts.py
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


def _svc():
    from service.attempt_service import AttemptService

    return object.__new__(AttemptService)


def test_hard_closed_only_for_archived():
    from utils.enums import TestStatus

    svc = _svc()
    closed = SimpleNamespace(
        status=TestStatus.CLOSED.value, archived_at=None, closed_at=datetime.now(timezone.utc)
    )
    archived = SimpleNamespace(
        status=TestStatus.ARCHIVED.value, archived_at=datetime.now(timezone.utc), closed_at=None
    )
    assert svc._is_test_hard_closed(closed) is False
    assert svc._is_test_hard_closed(archived) is True


def test_can_resume_closed_test_in_progress_attempt():
    from utils.enums import TestAttemptStatus, TestStatus

    svc = _svc()
    now = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    attempt = SimpleNamespace(
        status=TestAttemptStatus.IN_PROGRESS.value,
        expires_at=now + timedelta(minutes=30),
    )
    test = SimpleNamespace(
        status=TestStatus.CLOSED.value,
        archived_at=None,
        availability_time_mode="FLEXIBLE",
        closed_at=now,
        starts_at=None,
        duration_minutes=60,
    )
    with patch(
        "service.attempt_service.local_timezone_now", return_value=now
    ):
        assert svc._can_resume_attempt(attempt, test) is True


def test_cannot_start_new_attempt_when_closed():
    from utils.enums import TestStatus

    svc = _svc()
    test = SimpleNamespace(
        status=TestStatus.CLOSED.value,
        archived_at=None,
        closed_at=datetime.now(timezone.utc),
        availability_time_mode="FLEXIBLE",
        duration_minutes=60,
        starts_at=None,
    )
    assert svc._can_start_first_attempt(test) is False


def test_flexible_deadline_ignores_teacher_closed_at():
    svc = _svc()
    now = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    attempt = SimpleNamespace(expires_at=now + timedelta(minutes=20))
    test = SimpleNamespace(
        availability_time_mode="FLEXIBLE",
        closed_at=now,  # stamped at teacher close
        starts_at=None,
        duration_minutes=60,
    )
    deadline = svc._attempt_end_deadline(attempt, test)
    assert deadline == attempt.expires_at


def test_check_and_apply_timeout_does_not_finalize_on_closed_status_alone():
    from utils.enums import TestAttemptStatus, TestStatus

    svc = _svc()
    now = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    attempt = SimpleNamespace(
        id=1,
        test_id=9,
        status=TestAttemptStatus.IN_PROGRESS.value,
        expires_at=now + timedelta(minutes=15),
    )
    test = SimpleNamespace(
        id=9,
        status=TestStatus.CLOSED.value,
        availability_time_mode="FLEXIBLE",
        closed_at=now,
        archived_at=None,
        starts_at=None,
        duration_minutes=60,
    )
    svc._finalize_attempt = MagicMock()
    with patch(
        "service.attempt_service.local_timezone_now", return_value=now
    ):
        svc._check_and_apply_timeout(attempt, test)
    svc._finalize_attempt.assert_not_called()


def test_timeout_still_finalizes_after_close_when_expires_at_passed():
    """Scenario 2: CLOSED test + natural expires_at reached → TIMEOUT finalize."""
    from utils.enums import TestAttemptStatus, TestStatus

    svc = _svc()
    now = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    attempt = SimpleNamespace(
        id=1,
        test_id=9,
        status=TestAttemptStatus.IN_PROGRESS.value,
        expires_at=now - timedelta(minutes=1),
    )
    test = SimpleNamespace(
        id=9,
        status=TestStatus.CLOSED.value,
        availability_time_mode="FLEXIBLE",
        closed_at=now - timedelta(minutes=10),
        archived_at=None,
        starts_at=None,
        duration_minutes=60,
    )
    svc._finalize_attempt = MagicMock()
    with patch(
        "service.attempt_service.local_timezone_now", return_value=now
    ):
        svc._check_and_apply_timeout(attempt, test)
    svc._finalize_attempt.assert_called_once()
    kwargs = svc._finalize_attempt.call_args.kwargs
    assert kwargs["submission_source"] == "TIMEOUT"


def test_cannot_resume_submitted_attempt():
    """Scenario 4: SUBMITTED attempt cannot resume."""
    from utils.enums import TestAttemptStatus, TestStatus
    from service.exceptions import ConflictError

    svc = _svc()
    attempt = SimpleNamespace(status=TestAttemptStatus.SUBMITTED.value)
    test = SimpleNamespace(
        status=TestStatus.CLOSED.value,
        archived_at=None,
        availability_time_mode="FLEXIBLE",
    )
    try:
        svc._ensure_resume_allowed(attempt, test)
        raise AssertionError("expected ConflictError")
    except ConflictError:
        pass


def test_should_finalize_false_when_closed_with_time_remaining():
    from utils.enums import TestAttemptStatus, TestStatus

    svc = _svc()
    now = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    attempt = SimpleNamespace(
        status=TestAttemptStatus.IN_PROGRESS.value,
        expires_at=now + timedelta(minutes=20),
    )
    test = SimpleNamespace(
        status=TestStatus.CLOSED.value,
        archived_at=None,
        availability_time_mode="FLEXIBLE",
        closed_at=now,
        starts_at=None,
        duration_minutes=60,
    )
    assert svc._should_finalize_attempt(attempt, test, now) is False


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
