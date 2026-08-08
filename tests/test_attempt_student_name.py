"""Unit checks that attempt payloads include student_name.

Run: python tests/test_attempt_student_name.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_serialize_attempt_includes_student_name():
    from service.attempt_service import AttemptService

    svc = object.__new__(AttemptService)
    svc.tests = MagicMock()
    svc.grading = MagicMock()
    svc.grading.has_pending_review.return_value = False

    attempt = SimpleNamespace(
        id=11,
        test_id=5,
        student_membership_id=9,
        user_id=3,
        user=SimpleNamespace(full_name="Ahmad Ali", profile_image_url="https://cdn/a.png"),
        student_membership=None,
        test=None,
        status="SUBMITTED",
        started_at=None,
        submitted_at=None,
        expires_at=None,
        last_activity_at=None,
        submission_source="STUDENT",
        termination_reason=None,
        raw_score=80.0,
        final_score=None,
        percentage=None,
        graded_at=None,
    )
    svc.tests.get_by_id.return_value = SimpleNamespace(
        id=5,
        availability_time_mode="FLEXIBLE",
        starts_at=None,
        duration_minutes=60,
    )

    with patch.object(AttemptService, "_attempt_end_deadline", return_value=None):
        with patch.object(AttemptService, "_is_scheduled", return_value=False):
            with patch.object(
                AttemptService, "_availability_mode", return_value="FLEXIBLE"
            ):
                payload = AttemptService.serialize_attempt(
                    svc, attempt, include_answers=False
                )

    assert payload["student_name"] == "Ahmad Ali"
    assert payload["user_name"] == "Ahmad Ali"
    assert payload["attempt_id"] == 11
    assert payload["id"] == 11
    assert payload["student_avatar_url"] == "https://cdn/a.png"


def test_student_display_name_falls_back_to_membership_user():
    from service.attempt_service import AttemptService

    attempt = SimpleNamespace(
        user=None,
        student_membership=SimpleNamespace(
            user=SimpleNamespace(full_name="Sara Nasser")
        ),
    )
    assert AttemptService._student_display_name(attempt) == "Sara Nasser"


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
