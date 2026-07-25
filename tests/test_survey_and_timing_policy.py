"""
Lightweight unit checks for Survey / offline-grace policy helpers.

Run: python -m pytest tests/test_survey_and_timing_policy.py -q
(or: python tests/test_survey_and_timing_policy.py)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_create_schema_survey_requires_closed_at():
    from marshmallow import ValidationError
    from schemas.test_schema import CreateTestSchema

    schema = CreateTestSchema()
    try:
        schema.load(
            {
                "name": "Course Feedback",
                "subject_id": 1,
                "availability_time_mode": "SURVEY",
            }
        )
        assert False, "expected ValidationError"
    except ValidationError:
        pass


def test_create_schema_survey_rejects_duration():
    from marshmallow import ValidationError
    from schemas.test_schema import CreateTestSchema

    schema = CreateTestSchema()
    try:
        schema.load(
            {
                "name": "Course Feedback",
                "subject_id": 1,
                "availability_time_mode": "SURVEY",
                "closed_at": "2026-12-01T23:59:00",
                "duration_minutes": 30,
            }
        )
        assert False, "expected ValidationError"
    except ValidationError:
        pass


def test_create_schema_survey_keeps_duration_null():
    from schemas.test_schema import CreateTestSchema

    data = CreateTestSchema().load(
        {
            "name": "Course Feedback",
            "subject_id": 1,
            "availability_time_mode": "SURVEY",
            "closed_at": "2026-12-01T23:59:00",
        }
    )
    assert data.get("duration_minutes") is None
    assert data.get("closed_at") is not None


def test_create_schema_exam_omitted_duration_is_none_service_defaults():
    """Schema no longer injects 30; TestService applies exam default."""
    from schemas.test_schema import CreateTestSchema

    data = CreateTestSchema().load({"name": "Midterm", "subject_id": 1})
    assert data.get("duration_minutes") is None


def test_offline_grace_matrix():
    from service.test_service import TestService

    assert (
        TestService._resolve_offline_grace_minutes(
            mode="SCHEDULED", proctoring_enabled=False, offline_raw={}
        )
        == 5
    )
    assert (
        TestService._resolve_offline_grace_minutes(
            mode="SCHEDULED", proctoring_enabled=True, offline_raw={}
        )
        == 5
    )
    assert (
        TestService._resolve_offline_grace_minutes(
            mode="FLEXIBLE", proctoring_enabled=True, offline_raw={}
        )
        == 5
    )
    assert (
        TestService._resolve_offline_grace_minutes(
            mode="FLEXIBLE", proctoring_enabled=False, offline_raw={}
        )
        is None
    )
    assert (
        TestService._resolve_offline_grace_minutes(
            mode="SURVEY", proctoring_enabled=False, offline_raw={}
        )
        is None
    )


def test_availability_mode_includes_survey():
    from utils.enums import AvailabilityTimeMode

    assert AvailabilityTimeMode.SURVEY.value == "SURVEY"
    assert {m.value for m in AvailabilityTimeMode} == {
        "SCHEDULED",
        "FLEXIBLE",
        "SURVEY",
    }


def test_scheduled_starts_at_in_past_is_rejected():
    from datetime import datetime, timedelta
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo

    from service.exceptions import ValidationError
    from service.test_service import TestService
    from utils.messages import Messages

    tz = ZoneInfo("Asia/Damascus")
    past = datetime.now(tz) - timedelta(hours=3)
    test = SimpleNamespace(
        availability_time_mode="SCHEDULED",
        starts_at=past,
        closed_at=None,
        duration_minutes=60,
    )
    svc = object.__new__(TestService)
    try:
        svc._validate_test_timing_rules(test)
        assert False, "expected ValidationError for past starts_at"
    except ValidationError as exc:
        assert Messages.STARTS_AT_MUST_BE_IN_THE_FUTURE in str(exc)


def test_scheduled_starts_at_in_future_is_allowed():
    from datetime import datetime, timedelta
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo

    from service.test_service import TestService

    tz = ZoneInfo("Asia/Damascus")
    future = datetime.now(tz) + timedelta(hours=2)
    test = SimpleNamespace(
        availability_time_mode="SCHEDULED",
        starts_at=future,
        closed_at=None,
        duration_minutes=60,
    )
    svc = object.__new__(TestService)
    svc._validate_test_timing_rules(test)


def test_flexible_past_starts_at_is_allowed():
    """FLEXIBLE ignores starts_at for take-time; past value must not block PATCH."""
    from datetime import datetime, timedelta
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo

    from service.test_service import TestService

    tz = ZoneInfo("Asia/Damascus")
    past = datetime.now(tz) - timedelta(hours=3)
    test = SimpleNamespace(
        availability_time_mode="FLEXIBLE",
        starts_at=past,
        closed_at=None,
        duration_minutes=60,
    )
    svc = object.__new__(TestService)
    svc._validate_test_timing_rules(test)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("All checks passed.")
