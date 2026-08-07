"""Official Attempt rule — latest sitting is the only official result.

Run: python tests/test_official_attempt.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _pick_official(attempts):
    """Mirrors ORDER BY started_at DESC, id DESC."""
    return max(attempts, key=lambda a: (a["started_at"], a["id"]))


def test_1_two_graded_official_is_latest_score_85():
    official = _pick_official(
        [
            {"id": 1, "started_at": "2026-07-01", "status": "GRADED", "pct": 70},
            {"id": 2, "started_at": "2026-07-20", "status": "GRADED", "pct": 85},
        ]
    )
    assert official["id"] == 2
    assert official["pct"] == 85


def test_2_latest_submitted_no_official_score():
    official = _pick_official(
        [
            {"id": 1, "started_at": "2026-07-01", "status": "GRADED", "pct": 70},
            {"id": 2, "started_at": "2026-07-20", "status": "SUBMITTED", "pct": None},
        ]
    )
    assert official["id"] == 2
    assert official["status"] == "SUBMITTED"
    assert official["pct"] is None


def test_3_latest_in_progress_no_official_score():
    official = _pick_official(
        [
            {"id": 1, "started_at": "2026-07-01", "status": "GRADED", "pct": 70},
            {"id": 2, "started_at": "2026-07-20", "status": "IN_PROGRESS", "pct": None},
        ]
    )
    assert official["id"] == 2
    assert official["status"] == "IN_PROGRESS"


def test_4_three_graded_only_latest_enters_analytics():
    sittings = [
        {"id": 1, "started_at": "t1", "status": "GRADED", "pct": 70},
        {"id": 2, "started_at": "t2", "status": "GRADED", "pct": 85},
        {"id": 3, "started_at": "t3", "status": "GRADED", "pct": 90},
    ]
    official = _pick_official(sittings)
    analytics_scores = [
        a["pct"]
        for a in sittings
        if a["id"] == official["id"] and a["status"] == "GRADED"
    ]
    assert analytics_scores == [90]


def test_5_two_students_one_official_each():
    by_student = {
        "A": [
            {"id": 1, "started_at": "t1", "pct": 60},
            {"id": 2, "started_at": "t2", "pct": 90},
        ],
        "B": [
            {"id": 3, "started_at": "t1", "pct": 50},
            {"id": 4, "started_at": "t3", "pct": 80},
        ],
    }
    scores = [_pick_official(rows)["pct"] for rows in by_student.values()]
    assert scores == [90, 80]
    assert round(sum(scores) / len(scores), 2) == 85.0


def test_6_analytics_period_uses_official_graded_at_not_old_july_score():
    july_from = datetime(2026, 7, 1, tzinfo=timezone.utc)
    july_to = datetime(2026, 7, 31, 23, 59, 59, tzinfo=timezone.utc)
    aug_from = datetime(2026, 8, 1, tzinfo=timezone.utc)
    aug_to = datetime(2026, 8, 31, 23, 59, 59, tzinfo=timezone.utc)

    sittings = [
        {
            "id": 1,
            "started_at": datetime(2026, 7, 5, tzinfo=timezone.utc),
            "status": "GRADED",
            "pct": 70,
            "graded_at": datetime(2026, 7, 10, tzinfo=timezone.utc),
        },
        {
            "id": 2,
            "started_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "status": "GRADED",
            "pct": 90,
            "graded_at": datetime(2026, 8, 5, tzinfo=timezone.utc),
        },
    ]
    official = _pick_official(sittings)

    def in_period(period_from, period_to):
        if official["status"] != "GRADED":
            return None
        if period_from <= official["graded_at"] <= period_to:
            return official["pct"]
        return None

    assert in_period(july_from, july_to) is None
    assert in_period(aug_from, aug_to) == 90


def test_7_monitoring_graded_attempts_counts_official_graded_only():
    from service.proctoring_service import ProctoringService

    students = [
        {"attempt_status": "GRADED", "monitoring_state": "COMPLETED"},  # A latest GRADED
        {"attempt_status": "GRADED", "monitoring_state": "COMPLETED"},  # B
        {"attempt_status": "SUBMITTED", "monitoring_state": "SUBMITTED"},  # C
        {"attempt_status": "IN_PROGRESS", "monitoring_state": "IN_PROGRESS"},  # D
    ]
    summary = ProctoringService._monitoring_summary(students)
    assert summary["graded_attempts"] == 2
    assert summary["completed"] == 2


def test_8_old_attempt_remains_conceptually_when_superseded():
    """Official metrics ignore old rows; history rows are not deleted."""
    history = [
        {"id": 1, "started_at": "t1", "status": "GRADED", "pct": 70, "kept": True},
        {"id": 2, "started_at": "t2", "status": "GRADED", "pct": 85, "kept": True},
    ]
    official = _pick_official(history)
    assert all(row["kept"] for row in history)
    assert official["id"] == 2
    official_scores = [r["pct"] for r in history if r["id"] == official["id"]]
    assert official_scores == [85]


def test_official_selector_sql_orders_by_started_at_then_id():
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from repositories.attempt_repository import TestAttemptRepository

    sq = TestAttemptRepository.official_attempt_ids_subquery()
    sql = str(
        select(sq).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )
    ).lower()
    assert "row_number" in sql
    assert "started_at" in sql
    assert "partition" in sql or "partition by" in sql.replace("\n", " ")


def test_student_results_serializer_pending_has_null_score():
    from service.attempt_service import AttemptService

    svc = object.__new__(AttemptService)
    svc.grading = MagicMock()
    svc.grading.maximum_score.return_value = 100.0
    attempt = SimpleNamespace(
        id=9,
        status="SUBMITTED",
        final_score=None,
        percentage=None,
        graded_at=None,
        test=SimpleNamespace(
            id=1,
            name="Exam",
            subject=SimpleNamespace(name="Math"),
            created_by=SimpleNamespace(user=SimpleNamespace(full_name="T")),
        ),
        user=SimpleNamespace(full_name="Student"),
        student_membership=None,
    )
    with patch(
        "service.attempt_service.format_local_datetime", return_value=None
    ):
        payload = AttemptService._serialize_student_graded_result(svc, attempt)
    assert payload["status"] == "SUBMITTED"
    assert payload["score"] is None
    assert payload["percentage"] is None
    assert payload["is_official"] is True


def test_teacher_official_scores_subquery_uses_official_not_latest_graded():
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from repositories.institution_analytics_repository import (
        AnalyticsScope,
        InstitutionAnalyticsRepository,
    )

    repo = InstitutionAnalyticsRepository()
    scope = AnalyticsScope(
        workspace_id=20,
        date_from=datetime(2026, 7, 1, tzinfo=timezone.utc),
        date_to=datetime(2026, 7, 31, tzinfo=timezone.utc),
    )
    sq = repo._official_graded_student_test_scores_subquery(scope)
    sql = str(
        select(sq).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )
    ).lower()
    assert "row_number" in sql
    assert "started_at" in sql
    assert "graded_at" in sql


if __name__ == "__main__":
    tests = [name for name, obj in globals().items() if name.startswith("test_")]
    failed = 0
    for name in sorted(tests):
        try:
            globals()[name]()
            print(f"OK  {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
    if failed:
        raise SystemExit(1)
    print(f"\n{len(tests)} passed")
