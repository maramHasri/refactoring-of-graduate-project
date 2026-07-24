"""Lightweight checks for workspace dashboard helpers.

Run: python tests/test_workspace_dashboard.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

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
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from service.workspace_dashboard_service import WorkspaceDashboardService

    starts = datetime(2026, 7, 30, 9, 30, tzinfo=ZoneInfo("Asia/Damascus"))
    test = SimpleNamespace(
        id=9,
        name="Midterm",
        subject_id=3,
        subject=SimpleNamespace(name="Math"),
        starts_at=starts,
        closed_at=None,
        scheduled_publish_at=None,
        status="PUBLISHED",
        availability_time_mode="SCHEDULED",
    )
    payload = WorkspaceDashboardService._serialize_upcoming_test(test)
    assert payload["test_id"] == 9
    assert payload["subject_name"] == "Math"
    assert payload["status"] == "PUBLISHED"
    assert payload["exam_date"] == "2026-07-30"
    assert payload["exam_time"] == "09:30"


def test_member_count_shape():
    """Document expected count keys from repository contract."""
    expected = {"admins", "teachers", "students"}
    sample = {"admins": 1, "teachers": 2, "students": 10}
    assert set(sample) == expected
    assert sample["admins"] + sample["teachers"] + sample["students"] == 13


def _service_with_workspace(workspace):
    from service.workspace_dashboard_service import WorkspaceDashboardService

    svc = WorkspaceDashboardService()
    svc.workspaces = MagicMock()
    svc.workspaces.get_by_id.return_value = workspace
    return svc


def test_solo_owner_can_access_dashboard():
    workspace = SimpleNamespace(id=1, kind="SOLO", owner_membership_id=10)
    actor = SimpleNamespace(id=10, role="ADMIN")
    svc = _service_with_workspace(workspace)
    assert svc._ensure_dashboard_access(1, actor) is workspace


def test_institution_admin_can_access_dashboard():
    workspace = SimpleNamespace(id=2, kind="INSTITUTION", owner_membership_id=99)
    actor = SimpleNamespace(id=5, role="ADMIN")
    svc = _service_with_workspace(workspace)
    assert svc._ensure_dashboard_access(2, actor) is workspace


def test_institution_owner_can_access_dashboard():
    workspace = SimpleNamespace(id=3, kind="INSTITUTION", owner_membership_id=7)
    actor = SimpleNamespace(id=7, role="TEACHER")  # owner even without ADMIN role
    svc = _service_with_workspace(workspace)
    assert svc._ensure_dashboard_access(3, actor) is workspace


def test_student_cannot_access_dashboard():
    from service.exceptions import ForbiddenError

    workspace = SimpleNamespace(id=4, kind="SOLO", owner_membership_id=10)
    actor = SimpleNamespace(id=20, role="STUDENT")
    svc = _service_with_workspace(workspace)
    try:
        svc._ensure_dashboard_access(4, actor)
        assert False, "expected ForbiddenError"
    except ForbiddenError:
        pass


def test_teacher_non_owner_cannot_access_solo_dashboard():
    from service.exceptions import ForbiddenError

    workspace = SimpleNamespace(id=5, kind="SOLO", owner_membership_id=10)
    actor = SimpleNamespace(id=11, role="TEACHER")
    svc = _service_with_workspace(workspace)
    try:
        svc._ensure_dashboard_access(5, actor)
        assert False, "expected ForbiddenError"
    except ForbiddenError:
        pass


if __name__ == "__main__":
    test_dashboard_query_schema_defaults()
    test_dashboard_query_schema_bounds()
    test_dashboard_service_import_and_serialize()
    test_member_count_shape()
    test_solo_owner_can_access_dashboard()
    test_institution_admin_can_access_dashboard()
    test_institution_owner_can_access_dashboard()
    test_student_cannot_access_dashboard()
    test_teacher_non_owner_cannot_access_solo_dashboard()
    print("all workspace dashboard checks passed")
