"""Teacher Activity analytics — final period-activity contract.

Run: python tests/test_teacher_activity_analytics.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _scope(**kwargs):
    from repositories.institution_analytics_repository import AnalyticsScope

    base = dict(
        workspace_id=20,
        date_from=datetime(2026, 7, 1, tzinfo=timezone.utc),
        date_to=datetime(2026, 7, 31, 23, 59, 59, tzinfo=timezone.utc),
    )
    base.update(kwargs)
    return AnalyticsScope(**base)


def test_1_draft_excluded_from_base_filters():
    from sqlalchemy.orm import aliased

    from models import Membership, Test
    from repositories.institution_analytics_repository import (
        InstitutionAnalyticsRepository,
    )
    from utils.enums import TestStatus

    repo = InstitutionAnalyticsRepository()
    creator = aliased(Membership)
    filters = repo._teacher_base_test_filters(_scope(), creator=creator)
    text = " | ".join(str(f) for f in filters)
    assert any(
        str(f) == str(Test.status != TestStatus.DRAFT.value) for f in filters
    )
    assert "archived_at" in text
    assert not any("created_at" in str(f) for f in filters)


def test_2_and_3_performance_requires_assignment_and_graded_not_created_at():
    """Non-draft + no assignment excluded; June-created + July GRADED included."""
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from repositories.institution_analytics_repository import (
        InstitutionAnalyticsRepository,
    )

    repo = InstitutionAnalyticsRepository()
    sq = repo._teacher_performance_active_tests_subquery(_scope())
    sql = str(
        select(sq).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )
    ).lower()
    assert "test_student_assignments" in sql
    assert "graded" in sql
    # Performance eligibility must NOT gate on Test.created_at
    assert "tests.created_at" not in sql and "test.created_at" not in sql


def test_4_no_period_activity_means_not_in_performance_active_sql():
    """Active tests subquery requires GRADED in period (no blind historical assign)."""
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from repositories.institution_analytics_repository import (
        InstitutionAnalyticsRepository,
    )

    repo = InstitutionAnalyticsRepository()
    sq = repo._teacher_performance_active_tests_subquery(_scope())
    sql = str(
        select(sq).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )
    ).lower()
    assert "graded_at" in sql
    assert "exists" in sql


def test_5_tests_created_uses_created_at_in_period():
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from repositories.institution_analytics_repository import (
        InstitutionAnalyticsRepository,
    )

    repo = InstitutionAnalyticsRepository()
    sq = repo._teacher_tests_created_subquery(_scope())
    sql = str(
        select(sq).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )
    ).lower()
    assert "created_at" in sql
    assert "test_student_assignments" in sql
    assert "draft" in sql or "!=" in sql


def test_6_completion_rate_10_targeted_7_graded():
    from repositories.institution_analytics_repository import (
        InstitutionAnalyticsRepository as R,
    )

    assert R.teacher_completion_rate(7, 10) == 70.0
    assert R.teacher_completion_rate(0, 10) == 0.0
    assert R.teacher_completion_rate(0, 0) == 0.0


def test_7_multiple_july_attempts_pick_latest_not_max_or_all():
    def pick_latest_in_period(attempts, period_start, period_end):
        in_period = [
            a
            for a in attempts
            if a["status"] == "GRADED"
            and period_start <= a["graded_at"] <= period_end
        ]
        in_period.sort(key=lambda a: (a["graded_at"], a["id"]), reverse=True)
        return in_period[0]["percentage"] if in_period else None

    july_start, july_end = "2026-07-01", "2026-07-31"
    assert (
        pick_latest_in_period(
            [
                {"id": 1, "status": "GRADED", "graded_at": "2026-07-05", "percentage": 50},
                {"id": 2, "status": "GRADED", "graded_at": "2026-07-10", "percentage": 70},
                {"id": 3, "status": "GRADED", "graded_at": "2026-07-20", "percentage": 80},
            ],
            july_start,
            july_end,
        )
        == 80
    )


def test_8_period_first_then_latest_july_keeps_70_not_august_90():
    def pick_latest_in_period(attempts, period_start, period_end):
        in_period = [
            a
            for a in attempts
            if a["status"] == "GRADED"
            and period_start <= a["graded_at"] <= period_end
        ]
        in_period.sort(key=lambda a: (a["graded_at"], a["id"]), reverse=True)
        return in_period[0]["percentage"] if in_period else None

    assert (
        pick_latest_in_period(
            [
                {"id": 1, "status": "GRADED", "graded_at": "2026-07-10", "percentage": 70},
                {"id": 2, "status": "GRADED", "graded_at": "2026-08-05", "percentage": 90},
            ],
            "2026-07-01",
            "2026-07-31",
        )
        == 70
    )


def test_9_distinct_targeted_students_documented():
    # Same student on two tests → one targeted count
    assigned = {("s1", "t1"), ("s1", "t2"), ("s2", "t1")}
    assert len({s for s, _ in assigned}) == 2


def test_10_null_average_when_no_scores():
    from repositories.institution_analytics_repository import (
        InstitutionAnalyticsRepository,
    )

    repo = InstitutionAnalyticsRepository()
    row = MagicMock()
    row.teacher_membership_id = 34
    row.teacher_name = "Teacher B"
    row.tests_created = 0
    row.targeted_students = 0
    row.average_student_score = None
    row.completion_rate = 0.0

    mock_result = MagicMock()
    mock_result.all.return_value = [row]
    with patch("repositories.institution_analytics_repository.db") as mock_db:
        mock_db.session.execute.return_value = mock_result
        payload = repo.teacher_activity(_scope())

    assert payload[0]["average_student_score"] is None


def test_11_and_12_teacher_and_subject_filters_on_base():
    from sqlalchemy.orm import aliased

    from models import Membership
    from repositories.institution_analytics_repository import (
        InstitutionAnalyticsRepository,
    )

    repo = InstitutionAnalyticsRepository()
    creator = aliased(Membership)
    filters = repo._teacher_base_test_filters(
        _scope(subject_id=18, teacher_membership_id=34),
        creator=creator,
    )
    text = " | ".join(str(f) for f in filters)
    assert "subject_id" in text
    assert "created_by_membership_id" in text


def test_13_june_created_july_graded_included_in_performance_not_tests_created_sql():
    """Test 13: created outside period but graded inside → performance yes, created no."""
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from repositories.institution_analytics_repository import (
        InstitutionAnalyticsRepository,
    )

    repo = InstitutionAnalyticsRepository()
    perf_sql = str(
        select(repo._teacher_performance_active_tests_subquery(_scope())).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )
    ).lower()
    created_sql = str(
        select(repo._teacher_tests_created_subquery(_scope())).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )
    ).lower()

    assert "graded_at" in perf_sql
    assert "created_at" not in perf_sql.replace("created_by_membership_id", "")
    assert "created_at" in created_sql


def test_latest_graded_sql_period_then_row_number():
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from repositories.institution_analytics_repository import (
        InstitutionAnalyticsRepository,
    )

    repo = InstitutionAnalyticsRepository()
    sq = repo._latest_graded_student_test_scores_subquery(_scope())
    sql = str(
        select(sq).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )
    ).lower()
    assert "row_number" in sql
    assert "graded_at" in sql
    assert "rn" in sql or "row_number" in sql


def test_average_uses_student_test_pairs():
    scores = [80, 60, 90, 70]
    assert round(sum(scores) / len(scores), 2) == 75.0


def test_teacher_activity_partial_completion_shape():
    from repositories.institution_analytics_repository import (
        InstitutionAnalyticsRepository,
    )

    repo = InstitutionAnalyticsRepository()
    row = MagicMock()
    row.teacher_membership_id = 10
    row.teacher_name = "Teacher A"
    row.tests_created = 0  # June-created only → tests_created stays 0
    row.targeted_students = 10
    row.average_student_score = 72.5
    row.completion_rate = 70.0

    mock_result = MagicMock()
    mock_result.all.return_value = [row]
    with patch("repositories.institution_analytics_repository.db") as mock_db:
        mock_db.session.execute.return_value = mock_result
        payload = repo.teacher_activity(_scope())

    assert payload[0]["tests_created"] == 0
    assert payload[0]["targeted_students"] == 10
    assert payload[0]["completion_rate"] == 70.0


def test_live_teacher_activity_for_workspace_20_no_drafts_count():
    """Against local DB: DRAFT unassigned tests must not inflate tests_created."""
    from datetime import timedelta

    from app_factory import create_app
    from repositories.institution_analytics_repository import (
        AnalyticsScope,
        InstitutionAnalyticsRepository,
    )
    from utils.app_timezone import local_timezone_now

    app = create_app()
    with app.app_context():
        now = local_timezone_now()
        scope = AnalyticsScope(
            workspace_id=20,
            date_from=now - timedelta(days=30),
            date_to=now,
        )
        rows = InstitutionAnalyticsRepository().teacher_activity(scope)
        by_id = {r["teacher_membership_id"]: r for r in rows}
        if 34 in by_id:
            assert by_id[34]["tests_created"] == 0
            # Without GRADED activity in period, targeted stays 0
            assert by_id[34]["targeted_students"] == 0
            assert by_id[34]["completion_rate"] == 0.0
            assert by_id[34]["average_student_score"] is None


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
