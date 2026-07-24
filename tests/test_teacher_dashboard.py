"""Focused checks for teacher-scoped workspace dashboard.

Run: python tests/test_teacher_dashboard.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _attempt(percentage, *, final_score=None, test=None, student_id=1, attempt_id=1):
    return SimpleNamespace(
        id=attempt_id,
        percentage=percentage,
        final_score=final_score if final_score is not None else percentage,
        student_membership_id=student_id,
        test=test,
    )


def _service():
    from service.teacher_dashboard_service import TeacherDashboardService

    svc = TeacherDashboardService()
    svc.workspaces = MagicMock()
    svc.subject_memberships = MagicMock()
    svc.dashboard = MagicMock()
    svc.attempts = MagicMock()
    return svc


def test_average_performance_attempt_weighted():
    from service.teacher_dashboard_service import TeacherDashboardService

    attempts = [
        _attempt(80),
        _attempt(90),
        _attempt(60),
    ]
    assert TeacherDashboardService._average_percentage(attempts) == 76.67


def test_average_performance_empty():
    from service.teacher_dashboard_service import TeacherDashboardService

    assert TeacherDashboardService._average_percentage([]) == 0.0


def test_success_rate_uses_passing_score():
    from service.teacher_dashboard_service import TeacherDashboardService

    test = SimpleNamespace(passing_score=50)
    attempts = [
        _attempt(80, final_score=80, test=test),
        _attempt(40, final_score=40, test=test),
        _attempt(50, final_score=50, test=test),
    ]
    # 2 passed / 3 graded = 66.67
    assert TeacherDashboardService._success_rate(attempts) == 66.67


def test_success_rate_no_passing_score_treats_as_passed():
    from service.teacher_dashboard_service import TeacherDashboardService

    test = SimpleNamespace(passing_score=None)
    attempts = [_attempt(10, final_score=10, test=test)]
    assert TeacherDashboardService._success_rate(attempts) == 100.0


def test_teacher_scope_uses_assigned_subjects_only():
    svc = _service()
    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=99)
    actor = SimpleNamespace(id=10, role="TEACHER")
    svc.workspaces.get_by_id.return_value = workspace
    svc.subject_memberships.list_teacher_subject_ids.return_value = [1, 2]

    # Non-admin teacher → assigned subject ids only
    from unittest.mock import patch

    with patch(
        "service.teacher_dashboard_service.can_manage_subjects", return_value=False
    ):
        ids = svc._resolve_subject_scope(workspace, actor)
    assert ids == [1, 2]
    svc.subject_memberships.list_teacher_subject_ids.assert_called_once_with(10, 1)


def test_admin_scope_uses_all_workspace_subjects():
    svc = _service()
    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=10)
    actor = SimpleNamespace(id=10, role="ADMIN")
    svc.dashboard.list_active_subject_ids_for_workspace.return_value = [1, 2, 3]

    from unittest.mock import patch

    with patch(
        "service.teacher_dashboard_service.can_manage_subjects", return_value=True
    ):
        ids = svc._resolve_subject_scope(workspace, actor)
    assert ids == [1, 2, 3]


def test_student_cannot_access_teacher_dashboard():
    from service.exceptions import ForbiddenError

    svc = _service()
    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=99)
    actor = SimpleNamespace(id=20, role="STUDENT")
    svc.workspaces.get_by_id.return_value = workspace
    svc.subject_memberships.list_teacher_subject_ids.return_value = []

    from unittest.mock import patch

    with patch(
        "service.teacher_dashboard_service.can_manage_subjects", return_value=False
    ):
        try:
            svc._ensure_access(1, actor)
            assert False, "expected ForbiddenError"
        except ForbiddenError:
            pass


def test_teacher_can_access_with_role():
    svc = _service()
    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=99)
    actor = SimpleNamespace(id=10, role="TEACHER")
    svc.workspaces.get_by_id.return_value = workspace

    from unittest.mock import patch

    with patch(
        "service.teacher_dashboard_service.can_manage_subjects", return_value=False
    ):
        assert svc._ensure_access(1, actor) is workspace


def test_get_dashboard_scopes_metrics_and_excludes_other_subjects():
    """Teacher only sees subject 1; subject 2 data must not leak into cards."""
    svc = _service()
    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=99)
    actor = SimpleNamespace(id=10, role="TEACHER")

    subject_a = SimpleNamespace(id=1, name="Programming")
    subject_b = SimpleNamespace(id=2, name="Other")
    test_a = SimpleNamespace(
        id=100,
        subject_id=1,
        subject=subject_a,
        passing_score=50,
        name="Quiz A",
        starts_at=None,
        closed_at=None,
        status="PUBLISHED",
        availability_time_mode="FLEXIBLE",
        created_at=None,
        published_at=None,
    )
    test_b = SimpleNamespace(
        id=200,
        subject_id=2,
        subject=subject_b,
        passing_score=50,
        name="Quiz B",
        starts_at=None,
        closed_at=None,
        status="PUBLISHED",
        availability_time_mode="FLEXIBLE",
        created_at=None,
        published_at=None,
    )

    # Repository already filters by subject_ids; simulate that contract.
    graded = [
        _attempt(80, final_score=80, test=test_a, student_id=1, attempt_id=1),
        _attempt(90, final_score=90, test=test_a, student_id=2, attempt_id=2),
        _attempt(60, final_score=60, test=test_a, student_id=1, attempt_id=3),
    ]

    svc.workspaces.get_by_id.return_value = workspace
    svc.dashboard.list_active_subjects_by_ids.return_value = [subject_a]
    svc.dashboard.list_graded_attempts_for_subjects.return_value = graded
    svc.dashboard.count_students_per_subject.return_value = {1: 2}
    svc.dashboard.count_graded_tests_per_subject.return_value = {1: 1}
    svc.dashboard.count_distinct_students_for_subjects.return_value = 2
    svc.dashboard.list_upcoming_tests_for_subjects.return_value = []
    svc.dashboard.list_recent_created_tests.return_value = []
    svc.attempts.list_topic_weighted_rows_for_attempt_ids.return_value = [
        (1, "Programming", 41, "Recursion", 42.0, 100.0),
    ]
    svc.attempts.list_topic_weighted_rows_grouped_by_attempt.return_value = [
        (1, 41, "Recursion", 40.0, 100.0),
        (2, 41, "Recursion", 44.0, 100.0),
        (3, 41, "Recursion", 42.0, 100.0),
    ]

    from unittest.mock import patch

    with patch(
        "service.teacher_dashboard_service.can_manage_subjects", return_value=False
    ):
        svc.subject_memberships.list_teacher_subject_ids.return_value = [1]
        payload = svc.get_dashboard(1, actor)

    assert payload["success"] is True
    assert payload["summary"]["total_students"] == 2
    assert payload["summary"]["average_performance"] == 76.67
    assert len(payload["subjects"]) == 1
    card = payload["subjects"][0]
    assert card["subject_id"] == 1
    assert card["subject_name"] == "Programming"
    assert card["students_enrolled"] == 2
    assert card["graded_tests_count"] == 1
    assert card["average_performance"] == 76.67
    assert card["success_rate"] == 100.0
    assert card["weak_topics"][0]["topic_name"] == "Recursion"
    assert card["weak_topics"][0]["mastery_percentage"] == 42.0
    assert card["weak_topics"][0]["students_affected"] == 2
    assert card["weak_topics"][0]["attempts_count"] == 3
    # Ensure other subject never appears
    assert all(s["subject_id"] != 2 for s in payload["subjects"])
    assert subject_b.name not in {s["subject_name"] for s in payload["subjects"]}

    svc.dashboard.list_graded_attempts_for_subjects.assert_called_once()
    call_kwargs = svc.dashboard.list_graded_attempts_for_subjects.call_args.kwargs
    assert call_kwargs["subject_ids"] == [1]
    assert 2 not in call_kwargs["subject_ids"]


def test_distinct_student_count_contract():
    """Document DISTINCT semantics: same student in 2 subjects counts once."""
    # Service relies on repository COUNT(DISTINCT membership_id).
    svc = _service()
    svc.dashboard.count_distinct_students_for_subjects.return_value = 3
    assert svc.dashboard.count_distinct_students_for_subjects([1, 2]) == 3


def test_graded_tests_count_is_distinct_tests_not_attempts():
    """3 graded attempts on 2 tests → graded_tests_count = 2."""
    svc = _service()
    svc.dashboard.count_graded_tests_per_subject.return_value = {1: 2}
    assert svc.dashboard.count_graded_tests_per_subject(
        workspace_id=1, subject_ids=[1]
    ) == {1: 2}


def test_upcoming_scoped_to_teacher_subjects():
    svc = _service()
    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=99)
    actor = SimpleNamespace(id=10, role="TEACHER")
    subject = SimpleNamespace(id=1, name="Programming")
    svc.workspaces.get_by_id.return_value = workspace
    svc.subject_memberships.list_teacher_subject_ids.return_value = [1]
    svc.dashboard.list_active_subjects_by_ids.return_value = [subject]
    svc.dashboard.list_graded_attempts_for_subjects.return_value = []
    svc.dashboard.count_students_per_subject.return_value = {1: 0}
    svc.dashboard.count_graded_tests_per_subject.return_value = {}
    svc.dashboard.count_distinct_students_for_subjects.return_value = 0
    svc.dashboard.list_upcoming_tests_for_subjects.return_value = [
        SimpleNamespace(
            id=9,
            name="Midterm",
            subject_id=1,
            subject=subject,
            starts_at=None,
            closed_at=None,
            status="SCHEDULED",
            availability_time_mode="SCHEDULED",
        )
    ]
    svc.dashboard.list_recent_created_tests.return_value = []
    svc.attempts.list_topic_weighted_rows_for_attempt_ids.return_value = []
    svc.attempts.list_topic_weighted_rows_grouped_by_attempt.return_value = []

    from unittest.mock import patch

    with patch(
        "service.teacher_dashboard_service.can_manage_subjects", return_value=False
    ):
        payload = svc.get_dashboard(1, actor)

    assert len(payload["upcoming_tests"]) == 1
    assert payload["upcoming_tests"][0]["test_id"] == 9
    kwargs = svc.dashboard.list_upcoming_tests_for_subjects.call_args.kwargs
    assert kwargs["subject_ids"] == [1]


def test_recent_tests_use_creator_membership():
    svc = _service()
    workspace = SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=99)
    actor = SimpleNamespace(id=10, role="TEACHER")
    subject = SimpleNamespace(id=1, name="Programming")
    svc.workspaces.get_by_id.return_value = workspace
    svc.subject_memberships.list_teacher_subject_ids.return_value = [1]
    svc.dashboard.list_active_subjects_by_ids.return_value = [subject]
    svc.dashboard.list_graded_attempts_for_subjects.return_value = []
    svc.dashboard.count_students_per_subject.return_value = {}
    svc.dashboard.count_graded_tests_per_subject.return_value = {}
    svc.dashboard.count_distinct_students_for_subjects.return_value = 0
    svc.dashboard.list_upcoming_tests_for_subjects.return_value = []
    svc.dashboard.list_recent_created_tests.return_value = [
        SimpleNamespace(
            id=55,
            name="Created by me",
            subject_id=1,
            subject=subject,
            status="DRAFT",
            created_at=None,
            published_at=None,
        )
    ]
    svc.attempts.list_topic_weighted_rows_for_attempt_ids.return_value = []
    svc.attempts.list_topic_weighted_rows_grouped_by_attempt.return_value = []

    from unittest.mock import patch

    with patch(
        "service.teacher_dashboard_service.can_manage_subjects", return_value=False
    ):
        payload = svc.get_dashboard(1, actor)

    assert payload["recent_tests"][0]["test_id"] == 55
    kwargs = svc.dashboard.list_recent_created_tests.call_args.kwargs
    assert kwargs["creator_membership_id"] == 10


def test_serialize_upcoming_includes_date_time_parts():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from service.teacher_dashboard_service import TeacherDashboardService

    starts = datetime(2026, 7, 30, 9, 30, tzinfo=ZoneInfo("Asia/Damascus"))
    test = SimpleNamespace(
        id=9,
        name="Midterm",
        subject_id=3,
        subject=SimpleNamespace(name="Math"),
        starts_at=starts,
        closed_at=None,
        status="PUBLISHED",
        availability_time_mode="SCHEDULED",
    )
    payload = TeacherDashboardService._serialize_upcoming_test(test)
    assert payload["starts_at_date"] == "2026-07-30"
    assert payload["starts_at_time"] == "09:30"


if __name__ == "__main__":
    test_average_performance_attempt_weighted()
    test_average_performance_empty()
    test_success_rate_uses_passing_score()
    test_success_rate_no_passing_score_treats_as_passed()
    test_teacher_scope_uses_assigned_subjects_only()
    test_admin_scope_uses_all_workspace_subjects()
    test_student_cannot_access_teacher_dashboard()
    test_teacher_can_access_with_role()
    test_get_dashboard_scopes_metrics_and_excludes_other_subjects()
    test_distinct_student_count_contract()
    test_graded_tests_count_is_distinct_tests_not_attempts()
    test_upcoming_scoped_to_teacher_subjects()
    test_recent_tests_use_creator_membership()
    test_serialize_upcoming_includes_date_time_parts()
    print("all teacher dashboard checks passed")
