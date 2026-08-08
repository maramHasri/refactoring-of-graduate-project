"""Unit checks for scheduled auto-close sharing manual close logic.

Run: python tests/test_scheduled_auto_close.py
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


def test_close_test_uses_shared_apply_close():
    from service.test_service import TestService
    from utils.enums import TestStatus

    svc = object.__new__(TestService)
    test = SimpleNamespace(id=5, status=TestStatus.PUBLISHED.value)
    svc._resolve_test_access = MagicMock(return_value=test)

    with patch.object(TestService, "_apply_test_close") as apply_close:
        with patch("service.test_service.db") as mock_db:
            out = TestService.close_test(
                svc,
                test_id=5,
                workspace_id=1,
                actor_membership=SimpleNamespace(id=9),
            )

    apply_close.assert_called_once_with(test)
    mock_db.session.commit.assert_called_once()
    assert out is test


def test_apply_test_close_sets_status_without_finalizing_attempts():
    from service.test_service import TestService
    from utils.enums import TestStatus

    svc = object.__new__(TestService)
    test = SimpleNamespace(id=5, status=TestStatus.PUBLISHED.value, closed_at=None)
    fake_now = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)

    with patch(
        "service.test_service.local_timezone_now", return_value=fake_now
    ):
        with patch("service.attempt_service.AttemptService") as AttemptSvc:
            applied = TestService._apply_test_close(svc, test)

    assert applied is True
    assert test.status == TestStatus.CLOSED.value
    assert test.closed_at == fake_now
    AttemptSvc.assert_not_called()


def test_apply_test_close_preserves_future_planned_closed_at():
    from service.test_service import TestService
    from utils.enums import TestStatus

    svc = object.__new__(TestService)
    planned = datetime(2026, 7, 29, 18, 0, tzinfo=timezone.utc)
    test = SimpleNamespace(
        id=5, status=TestStatus.PUBLISHED.value, closed_at=planned
    )
    fake_now = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)

    with patch(
        "service.test_service.local_timezone_now", return_value=fake_now
    ):
        applied = TestService._apply_test_close(svc, test)

    assert applied is True
    assert test.status == TestStatus.CLOSED.value
    assert test.closed_at == planned


def test_apply_test_close_is_idempotent_when_already_closed():
    from service.test_service import TestService
    from utils.enums import TestStatus

    svc = object.__new__(TestService)
    original_closed_at = datetime(2026, 7, 29, 10, 0, tzinfo=timezone.utc)
    test = SimpleNamespace(
        id=5,
        status=TestStatus.CLOSED.value,
        closed_at=original_closed_at,
    )

    with patch("service.attempt_service.AttemptService") as AttemptSvc:
        applied = TestService._apply_test_close(svc, test)

    assert applied is False
    assert test.status == TestStatus.CLOSED.value
    assert test.closed_at == original_closed_at
    AttemptSvc.assert_not_called()


def test_close_due_scheduled_tests_closes_only_ended_windows():
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
    still_open = SimpleNamespace(
        id=11,
        status=TestStatus.PUBLISHED.value,
        starts_at=now - timedelta(minutes=10),
        duration_minutes=60,
    )
    svc.tests.list_published_scheduled_for_auto_close.return_value = [
        ended,
        still_open,
    ]

    with patch(
        "service.test_service.local_timezone_now", return_value=now
    ):
        with patch("service.attempt_service.AttemptService") as AttemptSvc:
            attempt_svc = AttemptSvc.return_value
            attempt_svc._scheduled_global_end_time.side_effect = (
                lambda test: test.starts_at
                + timedelta(minutes=int(test.duration_minutes))
            )
            with patch.object(
                TestService, "_apply_test_close", return_value=True
            ) as apply_close:
                with patch("service.test_service.db") as mock_db:
                    closed_ids = TestService.close_due_scheduled_tests(svc)

    assert closed_ids == [10]
    apply_close.assert_called_once_with(ended)
    mock_db.session.commit.assert_called_once()


def test_close_due_continues_after_one_test_fails():
    from service.test_service import TestService
    from utils.enums import TestStatus

    svc = object.__new__(TestService)
    svc.tests = MagicMock()
    now = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
    first = SimpleNamespace(
        id=10,
        status=TestStatus.PUBLISHED.value,
        starts_at=now - timedelta(hours=2),
        duration_minutes=60,
    )
    second = SimpleNamespace(
        id=11,
        status=TestStatus.PUBLISHED.value,
        starts_at=now - timedelta(hours=3),
        duration_minutes=60,
    )
    svc.tests.list_published_scheduled_for_auto_close.return_value = [first, second]

    def apply_side_effect(test):
        if test.id == 10:
            raise RuntimeError("boom")
        return True

    with patch(
        "service.test_service.local_timezone_now", return_value=now
    ):
        with patch("service.attempt_service.AttemptService") as AttemptSvc:
            AttemptSvc.return_value._scheduled_global_end_time.side_effect = (
                lambda test: test.starts_at
                + timedelta(minutes=int(test.duration_minutes))
            )
            with patch.object(
                TestService, "_apply_test_close", side_effect=apply_side_effect
            ):
                with patch("service.test_service.db") as mock_db:
                    closed_ids = TestService.close_due_scheduled_tests(svc)

    assert closed_ids == [11]
    mock_db.session.rollback.assert_called()
    mock_db.session.commit.assert_called_once()


def test_job_loop_order_publish_submit_close():
    from jobs import scheduled_test_publisher as job

    app = MagicMock()
    calls: list[str] = []

    def publish(app_arg):
        calls.append("publish")
        return [1]

    def submit(app_arg):
        calls.append("submit")
        return [2]

    def close(app_arg):
        calls.append("close")
        return [3]

    with patch.object(job, "_publish_due_tests", side_effect=publish):
        with patch.object(job, "_auto_submit_due_attempts", side_effect=submit):
            with patch.object(job, "_auto_close_due_tests", side_effect=close):
                with patch.object(job._stop_event, "wait", return_value=True):
                    job._run_loop(app, interval=1)

    assert calls == ["publish", "submit", "close"]


def test_sync_published_tests_past_window_closes_due_scheduled():
    from service.test_service import TestService
    from utils.enums import TestStatus

    svc = object.__new__(TestService)
    past = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    due = SimpleNamespace(
        id=1,
        status=TestStatus.PUBLISHED.value,
        availability_time_mode="SCHEDULED",
        closed_at=None,
    )
    future = SimpleNamespace(
        id=2,
        status=TestStatus.PUBLISHED.value,
        availability_time_mode="SCHEDULED",
        closed_at=None,
    )
    draft = SimpleNamespace(
        id=3,
        status=TestStatus.DRAFT.value,
        availability_time_mode="SCHEDULED",
        closed_at=None,
    )

    with patch("service.test_service.local_timezone_now", return_value=past + timedelta(hours=3)):
        with patch("service.test_service.db") as mock_db:
            with patch(
                "service.attempt_service.AttemptService._scheduled_global_end_time",
                side_effect=lambda t: past if t.id == 1 else past + timedelta(days=1),
            ):
                TestService._sync_published_tests_past_window(svc, [due, future, draft])

    assert due.status == TestStatus.CLOSED.value
    assert future.status == TestStatus.PUBLISHED.value
    assert draft.status == TestStatus.DRAFT.value
    mock_db.session.commit.assert_called_once()


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
