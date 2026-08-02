"""Unit tests for Super Admin Dashboard analytics improvements.

Run: python tests/test_super_admin_dashboard.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_add_months_helper():
    from repositories.super_admin_dashboard_repository import (
        SuperAdminDashboardRepository,
    )

    start = datetime(2026, 1, 31, tzinfo=timezone.utc)
    assert SuperAdminDashboardRepository._add_months(start, 1) == datetime(
        2026, 2, 28, tzinfo=timezone.utc
    )
    assert SuperAdminDashboardRepository._add_months(start, -1) == datetime(
        2025, 12, 31, tzinfo=timezone.utc
    )


def test_support_reports_maps_real_report_statuses():
    from repositories.super_admin_dashboard_repository import (
        SuperAdminDashboardRepository,
    )
    from utils.enums import ReportStatus

    repo = SuperAdminDashboardRepository()
    repo.reports = MagicMock()
    repo.reports.count_grouped_by_status.return_value = {
        ReportStatus.UNREAD.value: 2,
        ReportStatus.IN_REVIEW.value: 3,
        ReportStatus.REVIEWED.value: 4,
        ReportStatus.REJECTED.value: 1,
    }

    section = repo._support_reports_section()
    assert section == {
        "total": 10,
        "unread": 2,
        "in_review": 3,
        "resolved": 4,
        "rejected": 1,
    }
    repo.reports.count_grouped_by_status.assert_called_once_with()


def test_integrity_reports_maps_integrity_statuses_not_violations():
    from repositories.super_admin_dashboard_repository import (
        SuperAdminDashboardRepository,
    )
    from utils.enums import ProctoringIntegrityReportStatus

    repo = SuperAdminDashboardRepository()
    repo.integrity_reports = MagicMock()
    repo.integrity_reports.count_grouped_by_status.return_value = {
        ProctoringIntegrityReportStatus.PENDING.value: 5,
        ProctoringIntegrityReportStatus.CONFIRMED.value: 2,
        ProctoringIntegrityReportStatus.DISMISSED.value: 1,
    }

    section = repo._integrity_reports_section()
    assert section == {
        "total": 8,
        "pending": 5,
        "confirmed": 2,
        "dismissed": 1,
    }
    repo.integrity_reports.count_grouped_by_status.assert_called_once_with()


def test_content_section_reuses_question_bank_repository():
    from repositories.super_admin_dashboard_repository import (
        SuperAdminDashboardRepository,
    )

    repo = SuperAdminDashboardRepository()
    repo.question_banks = MagicMock()
    repo.question_banks.count_not_deleted.return_value = 42

    with patch.object(repo, "_content_section", wraps=repo._content_section):
        # Stub SQL counts for other content fields
        with patch(
            "repositories.super_admin_dashboard_repository.db"
        ) as mock_db:
            execute = mock_db.session.execute
            execute.return_value.scalar_one.side_effect = [10, 20, 30, 40]
            section = repo._content_section()

    assert section["question_banks"] == 42
    assert section["subjects"] == 10
    assert section["topics"] == 20
    assert section["questions"] == 30
    assert section["tests"] == 40
    repo.question_banks.count_not_deleted.assert_called_once_with()


def test_activity_series_fills_twelve_months():
    from repositories.super_admin_dashboard_repository import (
        SuperAdminDashboardRepository,
    )

    repo = SuperAdminDashboardRepository()
    now = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)

    jan = datetime(2026, 1, 1, tzinfo=timezone.utc)
    mar = datetime(2026, 3, 1, tzinfo=timezone.utc)

    with patch("repositories.super_admin_dashboard_repository.db") as mock_db:
        mock_db.session.execute.return_value.all.return_value = [
            (jan, 12),
            (mar, 5),
        ]
        series = repo._activity_series_section(now)

    assert series["period"] == "LAST_12_MONTHS"
    assert series["granularity"] == "MONTH"
    assert len(series["attempts"]) == 12
    assert series["attempts"][0]["month"] == "2025-09"
    assert series["attempts"][-1]["month"] == "2026-08"
    by_month = {row["month"]: row["count"] for row in series["attempts"]}
    assert by_month["2026-01"] == 12
    assert by_month["2026-03"] == 5
    assert by_month["2026-02"] == 0


def test_dashboard_schema_accepts_new_shape():
    from schemas.super_admin_dashboard_schema import SuperAdminDashboardSchema

    payload = {
        "users": {"total": 1},
        "organizations": {"total": 1, "most_active": []},
        "content": {
            "subjects": 1,
            "topics": 1,
            "question_banks": 1,
            "questions": 1,
            "tests": 1,
        },
        "tests": {"average_score": 80.0},
        "support_reports": {
            "total": 0,
            "unread": 0,
            "in_review": 0,
            "resolved": 0,
            "rejected": 0,
        },
        "integrity_reports": {
            "total": 0,
            "pending": 0,
            "confirmed": 0,
            "dismissed": 0,
        },
        "activity_series": {
            "period": "LAST_12_MONTHS",
            "granularity": "MONTH",
            "attempts": [{"month": "2026-01", "count": 0}],
        },
    }
    data = SuperAdminDashboardSchema().load(payload)
    assert "support_reports" in data
    assert "integrity_reports" in data
    assert "reports" not in data
    assert data["activity_series"]["period"] == "LAST_12_MONTHS"


def test_service_delegates_to_repository():
    from service.super_admin_dashboard_service import SuperAdminDashboardService

    svc = SuperAdminDashboardService()
    svc.repo = MagicMock()
    expected = {"users": {}, "support_reports": {}}
    svc.repo.build_dashboard.return_value = expected
    assert svc.get_dashboard() is expected
    svc.repo.build_dashboard.assert_called_once_with()


def test_route_uses_require_superadmin():
    import router.super_admin_dashboard_routes as routes

    source = Path(routes.__file__).read_text(encoding="utf-8")
    assert "@require_superadmin" in source
    assert 'route("/dashboard"' in source
    assert "get_super_admin_dashboard" in source


if __name__ == "__main__":
    tests = [
        test_add_months_helper,
        test_support_reports_maps_real_report_statuses,
        test_integrity_reports_maps_integrity_statuses_not_violations,
        test_content_section_reuses_question_bank_repository,
        test_activity_series_fills_twelve_months,
        test_dashboard_schema_accepts_new_shape,
        test_service_delegates_to_repository,
        test_route_uses_require_superadmin,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc}")
    if failed:
        raise SystemExit(1)
    print(f"OK {len(tests)} tests")
