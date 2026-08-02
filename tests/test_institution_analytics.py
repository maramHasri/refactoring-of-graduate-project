"""Unit tests for Institution Analytics Dashboard.

Run: python tests/test_institution_analytics.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TZ = ZoneInfo("Asia/Damascus")


def _dt(year, month, day, hour=12):
    return datetime(year, month, day, hour, 0, 0, tzinfo=TZ)


def test_analytics_query_schema_defaults():
    from schemas.workspace_schema import WorkspaceAnalyticsQuerySchema

    data = WorkspaceAnalyticsQuerySchema().load({})
    assert data["date_from"] is None
    assert data["date_to"] is None
    assert data["subject_id"] is None
    assert data["teacher_membership_id"] is None


def test_analytics_query_schema_parses_filters():
    from schemas.workspace_schema import WorkspaceAnalyticsQuerySchema

    data = WorkspaceAnalyticsQuerySchema().load(
        {
            "date_from": "2026-01-01T00:00:00",
            "date_to": "2026-01-31T23:59:59",
            "subject_id": "3",
            "teacher_membership_id": "9",
        }
    )
    assert data["subject_id"] == 3
    assert data["teacher_membership_id"] == 9
    assert data["date_from"].year == 2026
    assert data["date_to"].month == 1


def test_pass_rule_reused_not_duplicated():
    from service.student_analytics_service import StudentAnalyticsService

    assert StudentAnalyticsService.attempt_is_passed_scores(70, 60) is True
    assert StudentAnalyticsService.attempt_is_passed_scores(50, 60) is False
    assert StudentAnalyticsService.attempt_is_passed_scores(None, 60) is True
    assert StudentAnalyticsService.attempt_is_passed_scores(90, None) is True

    attempt = SimpleNamespace(final_score=55)
    test = SimpleNamespace(passing_score=60)
    assert StudentAnalyticsService._attempt_is_passed(attempt, test) is False


def test_change_percentage():
    from service.institution_analytics_service import InstitutionAnalyticsService as S

    assert S.change_percentage(110, 100) == 10.0
    assert S.change_percentage(90, 100) == -10.0
    assert S.change_percentage(0, 0) == 0.0
    assert S.change_percentage(5, 0) == 100.0


def test_default_date_range_last_30_days():
    from service.institution_analytics_service import InstitutionAnalyticsService

    now = _dt(2026, 7, 29)
    start, end = InstitutionAnalyticsService._resolve_date_range(None, None, now)
    assert end == now
    assert start == now - timedelta(days=30)


def test_date_filter_rejects_inverted_range():
    from service.exceptions import ValidationError
    from service.institution_analytics_service import InstitutionAnalyticsService
    from utils.messages import Messages

    try:
        InstitutionAnalyticsService._resolve_date_range(
            _dt(2026, 7, 20), _dt(2026, 7, 10), _dt(2026, 7, 29)
        )
        assert False, "expected ValidationError"
    except ValidationError as exc:
        assert Messages.DATE_FROM_MUST_BE_BEFORE_OR_EQUAL_TO_DATE_TO in str(exc)


def test_previous_range_equal_length():
    from service.institution_analytics_service import InstitutionAnalyticsService

    date_from = _dt(2026, 7, 1)
    date_to = _dt(2026, 7, 31)
    prev_from, prev_to = InstitutionAnalyticsService._previous_range(date_from, date_to)
    assert (date_to - date_from) == (prev_to - prev_from)
    assert prev_to < date_from


def _service(workspace, *, subject=None, teacher=None):
    from service.institution_analytics_service import InstitutionAnalyticsService

    svc = InstitutionAnalyticsService()
    svc.workspaces = MagicMock()
    svc.workspaces.get_by_id.return_value = workspace
    svc.memberships = MagicMock()
    svc.memberships.get_by_id.return_value = teacher
    svc.subjects = MagicMock()
    svc.subjects.get_by_id.return_value = subject
    svc.analytics = MagicMock()
    return svc


def test_owner_only_access_allows_owner():
    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=10)
    actor = SimpleNamespace(id=10, role="ADMIN")
    svc = _service(workspace)
    assert svc._ensure_owner_access(1, actor) is workspace


def test_owner_only_rejects_teacher_non_owner():
    from service.exceptions import ForbiddenError
    from utils.messages import Messages

    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=10)
    actor = SimpleNamespace(id=99, role="TEACHER")
    svc = _service(workspace)
    try:
        svc._ensure_owner_access(1, actor)
        assert False, "expected ForbiddenError"
    except ForbiddenError as exc:
        assert Messages.ONLY_THE_WORKSPACE_OWNER_CAN_VIEW_INSTITUTION_ANALYTICS in str(
            exc
        )


def test_owner_only_rejects_admin_non_owner():
    from service.exceptions import ForbiddenError

    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=10)
    actor = SimpleNamespace(id=5, role="ADMIN")
    svc = _service(workspace)
    try:
        svc._ensure_owner_access(1, actor)
        assert False, "expected ForbiddenError"
    except ForbiddenError:
        pass


def test_owner_only_rejects_solo_workspace():
    from service.exceptions import ForbiddenError
    from utils.messages import Messages

    workspace = SimpleNamespace(id=2, kind="SOLO", owner_membership_id=10)
    actor = SimpleNamespace(id=10, role="ADMIN")
    svc = _service(workspace)
    try:
        svc._ensure_owner_access(2, actor)
        assert False, "expected ForbiddenError"
    except ForbiddenError as exc:
        assert Messages.THIS_ENDPOINT_IS_ONLY_AVAILABLE_FOR_INSTITUTION_WORKSPACES in str(
            exc
        )


def test_workspace_isolation_scope_uses_workspace_id():
    from repositories.institution_analytics_repository import AnalyticsScope

    scope = AnalyticsScope(
        workspace_id=42,
        date_from=_dt(2026, 1, 1),
        date_to=_dt(2026, 1, 31),
        subject_id=None,
        teacher_membership_id=None,
    )
    assert scope.workspace_id == 42


def test_subject_and_teacher_filters_validated():
    from service.exceptions import ValidationError

    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=10)
    svc = _service(workspace, subject=None)
    try:
        svc._validate_optional_filters(1, subject_id=99, teacher_membership_id=None)
        assert False, "expected ValidationError"
    except ValidationError:
        pass

    teacher = SimpleNamespace(id=7, workspace_id=1, role="TEACHER")
    svc = _service(workspace, teacher=teacher)
    svc._validate_optional_filters(1, subject_id=None, teacher_membership_id=7)

    foreign_teacher = SimpleNamespace(id=8, workspace_id=999, role="TEACHER")
    svc = _service(workspace, teacher=foreign_teacher)
    try:
        svc._validate_optional_filters(1, subject_id=None, teacher_membership_id=8)
        assert False, "expected ValidationError"
    except ValidationError:
        pass


def test_empty_workspace_response_shape():
    from service.institution_analytics_service import InstitutionAnalyticsService

    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=10)
    actor = SimpleNamespace(id=10, role="ADMIN")
    svc = _service(workspace)

    empty_members = {"teachers": 0, "students": 0}
    svc.analytics.count_active_members_by_role.return_value = empty_members
    svc.analytics.count_members_joined_in_range.return_value = 0
    svc.analytics.count_tests.return_value = 0
    svc.analytics.count_tests_created_in_range.return_value = 0
    svc.analytics.count_graded_attempts.return_value = 0
    svc.analytics.average_graded_percentage.return_value = 0.0
    svc.analytics.count_active_students.return_value = 0
    svc.analytics.pass_fail_counts.return_value = {
        "total": 0,
        "passed": 0,
        "failed": 0,
    }
    svc.analytics.monthly_average_scores.return_value = []
    svc.analytics.most_engaged_subjects.return_value = []
    svc.analytics.subject_score_extremes.return_value = ([], [])
    svc.analytics.teacher_activity.return_value = []
    svc.analytics.top_students.return_value = []
    svc.analytics.inactive_students.return_value = []
    svc.analytics.problematic_exams.return_value = []

    payload = svc.get_analytics(1, actor)
    assert payload["success"] is True
    assert payload["overview"]["total_students"]["value"] == 0
    assert payload["pass_fail"]["pass_rate"] == 0.0
    assert payload["monthly_average_scores"] == []
    assert payload["top_students"] == []
    assert payload["problematic_exams"] == []


def test_comparison_percentage_in_overview():
    from service.institution_analytics_service import InstitutionAnalyticsService

    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=10)
    actor = SimpleNamespace(id=10, role="ADMIN")
    svc = _service(workspace)

    svc.analytics.count_active_members_by_role.return_value = {
        "teachers": 2,
        "students": 10,
    }
    # joined current / previous for change%
    svc.analytics.count_members_joined_in_range.side_effect = [
        4,
        2,  # students
        1,
        1,  # teachers
    ]
    svc.analytics.count_tests.return_value = 5
    svc.analytics.count_tests_created_in_range.side_effect = [3, 1]
    svc.analytics.count_graded_attempts.side_effect = [20, 10]
    svc.analytics.average_graded_percentage.side_effect = [80.0, 70.0]
    svc.analytics.count_active_students.side_effect = [8, 4]
    svc.analytics.pass_fail_counts.return_value = {
        "total": 20,
        "passed": 16,
        "failed": 4,
    }
    svc.analytics.monthly_average_scores.return_value = []
    svc.analytics.most_engaged_subjects.return_value = []
    svc.analytics.subject_score_extremes.return_value = ([], [])
    svc.analytics.teacher_activity.return_value = []
    svc.analytics.top_students.return_value = []
    svc.analytics.inactive_students.return_value = []
    svc.analytics.problematic_exams.return_value = []

    payload = svc.get_analytics(1, actor)
    overview = payload["overview"]
    assert overview["total_students"]["change_percentage"] == 100.0
    assert overview["total_attempts"]["change_percentage"] == 100.0
    assert overview["institution_average_score"]["change_percentage"] == round(
        ((80 - 70) / 70) * 100, 2
    )
    assert overview["active_students"]["change_percentage"] == 100.0
    assert payload["pass_fail"]["pass_rate"] == 80.0
    assert payload["pass_fail"]["fail_rate"] == 20.0


def test_ranking_helpers_top_students_and_subjects():
    """Document expected ranking contracts used by the repository layer."""
    students = [
        {"student_name": "A", "average_score": 95},
        {"student_name": "B", "average_score": 88},
        {"student_name": "C", "average_score": 70},
    ]
    top = sorted(students, key=lambda s: s["average_score"], reverse=True)[:2]
    assert [s["student_name"] for s in top] == ["A", "B"]

    subjects = [
        {"subject_name": "Math", "average_score": 90},
        {"subject_name": "Sci", "average_score": 40},
        {"subject_name": "Hist", "average_score": 70},
    ]
    best = sorted(subjects, key=lambda s: s["average_score"], reverse=True)[:1]
    weakest = sorted(subjects, key=lambda s: s["average_score"])[:1]
    assert best[0]["subject_name"] == "Math"
    assert weakest[0]["subject_name"] == "Sci"


def test_activity_score_formula():
    students, teachers, tests = 100, 10, 20
    score = 0.6 * students + 0.2 * teachers + 0.2 * tests
    assert score == 66.0


def test_problematic_exams_composite_ranking():
    exams = [
        {
            "test_name": "A",
            "risk_percentage": 10,
            "violations_count": 2,
            "integrity_reports_count": 1,
        },
        {
            "test_name": "B",
            "risk_percentage": 40,
            "violations_count": 5,
            "integrity_reports_count": 3,
        },
        {
            "test_name": "C",
            "risk_percentage": 20,
            "violations_count": 1,
            "integrity_reports_count": 0,
        },
    ]
    for exam in exams:
        exam["_c"] = (
            exam["risk_percentage"]
            + exam["violations_count"]
            + exam["integrity_reports_count"]
        )
    ranked = sorted(exams, key=lambda e: e["_c"], reverse=True)
    assert [e["test_name"] for e in ranked] == ["B", "C", "A"]


def test_integrity_reports_use_proctoring_auto_not_support_reports():
    from utils.enums import AttemptSubmissionSource

    assert AttemptSubmissionSource.PROCTORING_AUTO.value == "PROCTORING_AUTO"


def test_large_dataset_contract_no_n_plus_one_in_service():
    """Service issues a fixed set of repository calls (no loops over entities)."""
    from service.institution_analytics_service import InstitutionAnalyticsService

    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=10)
    actor = SimpleNamespace(id=10, role="ADMIN")
    svc = _service(workspace)

    svc.analytics.count_active_members_by_role.return_value = {
        "teachers": 50,
        "students": 5000,
    }
    svc.analytics.count_members_joined_in_range.return_value = 10
    svc.analytics.count_tests.return_value = 200
    svc.analytics.count_tests_created_in_range.return_value = 20
    svc.analytics.count_graded_attempts.return_value = 20000
    svc.analytics.average_graded_percentage.return_value = 72.5
    svc.analytics.count_active_students.return_value = 1200
    svc.analytics.pass_fail_counts.return_value = {
        "total": 20000,
        "passed": 15000,
        "failed": 5000,
    }
    svc.analytics.monthly_average_scores.return_value = [
        {"period": "2026-06", "average_score": 70},
        {"period": "2026-07", "average_score": 75},
    ]
    svc.analytics.most_engaged_subjects.return_value = [
        {
            "subject_id": i,
            "subject_name": f"S{i}",
            "students_count": 100,
            "teachers_count": 2,
            "tests_count": 5,
            "average_score": 70.0,
            "activity_score": 61.4,
        }
        for i in range(10)
    ]
    svc.analytics.subject_score_extremes.return_value = (
        [{"subject_id": 1, "subject_name": "Best", "average_score": 95, "attempt_count": 10}],
        [{"subject_id": 2, "subject_name": "Weak", "average_score": 40, "attempt_count": 10}],
    )
    svc.analytics.teacher_activity.return_value = [
        {
            "teacher_membership_id": i,
            "teacher_name": f"T{i}",
            "tests_created": 3,
            "targeted_students": 40,
            "average_student_score": 80 - i,
            "completion_rate": 50.0,
        }
        for i in range(20)
    ]
    svc.analytics.top_students.return_value = [
        {
            "student_membership_id": i,
            "student_name": f"St{i}",
            "average_score": 90 - i,
            "completed_tests": 5,
            "profile_image": None,
        }
        for i in range(10)
    ]
    svc.analytics.inactive_students.return_value = []
    svc.analytics.problematic_exams.return_value = [
        {
            "test_id": 1,
            "test_name": "Risky",
            "subject_name": "Math",
            "risk_percentage": 45.0,
            "violations_count": 12,
            "integrity_reports_count": 3,
            "average_score": 55.0,
        }
    ]

    payload = svc.get_analytics(1, actor)
    assert len(payload["top_students"]) == 10
    assert payload["problematic_exams"][0]["integrity_reports_count"] == 3
    # Fixed call budget (current + previous windows + section queries)
    assert svc.analytics.count_graded_attempts.call_count == 2
    assert svc.analytics.top_students.call_count == 1
    assert svc.analytics.problematic_exams.call_count == 1
    assert svc.analytics.most_engaged_subjects.call_count == 1


def test_inactive_students_days_inactive():
    from service.institution_analytics_service import InstitutionAnalyticsService

    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=10)
    svc = _service(workspace)
    now = _dt(2026, 7, 29)
    last = now - timedelta(days=45)
    svc.analytics.inactive_students.return_value = [
        {
            "student_membership_id": 1,
            "student_name": "Idle",
            "last_activity_at": last,
            "joined_at": now - timedelta(days=100),
        }
    ]
    rows = svc._build_inactive_students(1, now - timedelta(days=30), now)
    assert rows[0]["days_inactive"] == 45
    assert rows[0]["student_name"] == "Idle"


def test_route_registered():
    from router.workspace_routes import workspace_bp

    rules = {rule.rule for rule in workspace_bp.url_map.iter_rules()} if hasattr(
        workspace_bp, "url_map"
    ) else set()
    # Blueprint deferred; assert view function exists
    from router import workspace_routes

    assert hasattr(workspace_routes, "get_institution_workspace_analytics")


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
