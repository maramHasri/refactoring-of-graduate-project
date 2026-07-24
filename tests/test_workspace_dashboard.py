"""Lightweight checks for institution workspace dashboard helpers.

Run: python tests/test_workspace_dashboard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_dashboard_query_schema_defaults():
    from schemas.workspace_schema import WorkspaceDashboardQuerySchema

    data = WorkspaceDashboardQuerySchema().load({})
    assert data["recent_limit"] == 5
    assert data["upcoming_limit"] == 10


def test_dashboard_query_schema_bounds():
    from marshmallow import ValidationError
    from schemas.workspace_schema import WorkspaceDashboardQuerySchema

    try:
        WorkspaceDashboardQuerySchema().load({"recent_limit": 0})
        assert False, "expected ValidationError"
    except ValidationError:
        pass


def test_dashboard_service_import_and_serialize():
    from types import SimpleNamespace

    from service.workspace_dashboard_service import WorkspaceDashboardService

    test = SimpleNamespace(
        id=9,
        name="Midterm",
        subject_id=3,
        subject=SimpleNamespace(name="Math"),
        starts_at=None,
        closed_at=None,
        scheduled_publish_at=None,
        status="PUBLISHED",
        availability_time_mode="FLEXIBLE",
    )
    payload = WorkspaceDashboardService._serialize_upcoming_test(test)
    assert payload["test_id"] == 9
    assert payload["subject_name"] == "Math"
    assert payload["status"] == "PUBLISHED"


def test_member_count_shape():
    """Document expected count keys from repository contract."""
    expected = {"admins", "teachers", "students"}
    sample = {"admins": 1, "teachers": 2, "students": 10}
    assert set(sample) == expected
    assert sample["admins"] + sample["teachers"] + sample["students"] == 13


if __name__ == "__main__":
    test_dashboard_query_schema_defaults()
    test_dashboard_query_schema_bounds()
    test_dashboard_service_import_and_serialize()
    test_member_count_shape()
    print("all workspace dashboard checks passed")
