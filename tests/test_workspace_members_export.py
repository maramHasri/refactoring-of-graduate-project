"""Tests for workspace students/teachers CSV export.

Run: python tests/test_workspace_members_export.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TZ = ZoneInfo("Asia/Damascus")


def test_csv_helper_includes_utf8_bom_and_headers():
    from utils.csv_download import CSV_BOM, build_csv_download_response

    with patch("utils.csv_download.Response", side_effect=lambda *a, **k: SimpleNamespace(data=a[0], headers=k.get("headers"), mimetype=k.get("mimetype"))):
        resp = build_csv_download_response(
            filename="students_2026-08-02.csv",
            headers=["Full Name", "Email"],
            rows=[["Ali", "a@x.com"]],
        )
    text = resp.data.decode("utf-8")
    assert text.startswith(CSV_BOM)
    assert "Full Name,Email" in text
    assert "Ali,a@x.com" in text
    assert "students_2026-08-02.csv" in resp.headers["Content-Disposition"]
    assert "csv" in resp.mimetype


def test_export_schema_search_only():
    from schemas.workspace_schema import WorkspaceMembersExportQuerySchema

    data = WorkspaceMembersExportQuerySchema().load({})
    assert data["search"] is None
    data = WorkspaceMembersExportQuerySchema().load({"search": "ali"})
    assert data["search"] == "ali"


def _owner_svc(workspace):
    from service.workspace_service import WorkspaceService

    svc = WorkspaceService()
    svc.workspaces = MagicMock()
    svc.workspaces.get_by_id.return_value = workspace
    svc.memberships = MagicMock()
    svc.student_groups = MagicMock()
    svc.tests = MagicMock()
    return svc


def test_students_export_owner_success_and_columns():
    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=10)
    actor = SimpleNamespace(id=10, role="ADMIN")
    svc = _owner_svc(workspace)

    joined = datetime(2026, 1, 15, 10, 0, tzinfo=TZ)
    membership = SimpleNamespace(
        id=30, status="ACTIVE", joined_at=joined, created_at=joined
    )
    user = SimpleNamespace(full_name="Student One", email="s1@ex.com")
    svc.memberships.list_active_members_by_role_with_subject_counts.return_value = (
        [(membership, user, 3)],
        1,
    )
    svc.student_groups.count_groups_by_student_membership_ids.return_value = {30: 2}

    with patch("utils.csv_download.Response", side_effect=lambda *a, **k: SimpleNamespace(data=a[0], headers=k["headers"], mimetype=k["mimetype"])):
        resp = svc.export_workspace_students_csv(1, actor, search="Student")

    text = resp.data.decode("utf-8")
    assert text.startswith("\ufeff")
    assert "Full Name,Email,Joined At,Membership Status,Enrolled Subjects Count,Student Groups Count" in text
    assert "Student One,s1@ex.com" in text
    assert ",ACTIVE,3,2" in text
    assert "membership_id" not in text.lower() or "Membership Status" in text
    assert "30" not in text.split("\n")[1]  # no internal id in data row
    call_kw = svc.memberships.list_active_members_by_role_with_subject_counts.call_args
    assert call_kw.kwargs.get("limit") is None
    assert call_kw.kwargs.get("search") == "Student"


def test_students_export_rejects_non_owner():
    from service.exceptions import ForbiddenError

    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=10)
    actor = SimpleNamespace(id=99, role="ADMIN")
    svc = _owner_svc(workspace)
    try:
        svc.export_workspace_students_csv(1, actor)
        assert False, "expected ForbiddenError"
    except ForbiddenError:
        pass


def test_students_export_workspace_isolation_uses_workspace_id():
    workspace = SimpleNamespace(id=42, kind="INSTITUTION", owner_membership_id=10)
    actor = SimpleNamespace(id=10, role="ADMIN")
    svc = _owner_svc(workspace)
    svc.memberships.list_active_members_by_role_with_subject_counts.return_value = ([], 0)
    svc.student_groups.count_groups_by_student_membership_ids.return_value = {}

    with patch("utils.csv_download.Response", side_effect=lambda *a, **k: SimpleNamespace(data=a[0], headers=k["headers"], mimetype=k["mimetype"])):
        svc.export_workspace_students_csv(42, actor)

    args = svc.memberships.list_active_members_by_role_with_subject_counts.call_args
    assert args.args[0] == 42
    assert svc.student_groups.count_groups_by_student_membership_ids.call_args.args[0] == 42


def test_teachers_export_owner_success():
    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=10)
    actor = SimpleNamespace(id=10, role="ADMIN")
    svc = _owner_svc(workspace)
    joined = datetime(2026, 2, 1, 8, 0, tzinfo=TZ)
    membership = SimpleNamespace(
        id=55, status="ACTIVE", joined_at=joined, created_at=joined
    )
    user = SimpleNamespace(full_name="Teacher A", email="t@ex.com")
    svc.memberships.list_active_members_by_role_with_subject_counts.return_value = (
        [(membership, user, 4)],
        1,
    )
    svc.tests.count_created_by_membership_ids.return_value = {55: 7}

    with patch("utils.csv_download.Response", side_effect=lambda *a, **k: SimpleNamespace(data=a[0], headers=k["headers"], mimetype=k["mimetype"])):
        resp = svc.export_workspace_teachers_csv(1, actor, search="Teach")

    text = resp.data.decode("utf-8")
    assert text.startswith("\ufeff")
    assert "Assigned Subjects Count,Tests Created Count" in text
    assert "Teacher A,t@ex.com" in text
    assert ",ACTIVE,4,7" in text
    assert "teachers_" in resp.headers["Content-Disposition"]


def test_teachers_export_rejects_solo_and_non_owner():
    from service.exceptions import ForbiddenError

    solo = SimpleNamespace(id=2, kind="SOLO", owner_membership_id=10)
    owner = SimpleNamespace(id=10, role="ADMIN")
    svc = _owner_svc(solo)
    try:
        svc.export_workspace_teachers_csv(2, owner)
        assert False, "expected ForbiddenError"
    except ForbiddenError:
        pass

    inst = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=10)
    teacher = SimpleNamespace(id=55, role="TEACHER")
    svc = _owner_svc(inst)
    try:
        svc.export_workspace_teachers_csv(1, teacher)
        assert False, "expected ForbiddenError"
    except ForbiddenError:
        pass


def test_routes_registered():
    from flask import Flask
    from router.workspace_routes import workspace_bp

    app = Flask(__name__)
    app.register_blueprint(workspace_bp, url_prefix="/workspaces")
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/workspaces/students/export" in rules
    assert "/workspaces/teachers/export" in rules


if __name__ == "__main__":
    tests = [name for name, obj in globals().items() if name.startswith("test_")]
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
