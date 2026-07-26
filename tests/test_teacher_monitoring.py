"""Focused unit checks for teacher test monitoring snapshot.

Run: python tests/test_teacher_monitoring.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _svc():
    from service.proctoring_service import ProctoringService

    svc = object.__new__(ProctoringService)
    svc.sessions = MagicMock()
    svc.events = MagicMock()
    svc.violations = MagicMock()
    svc.evidence = MagicMock()
    svc.audit_logs = MagicMock()
    svc.attempts = MagicMock()
    svc.test_questions = MagicMock()
    svc.assignments = MagicMock()
    svc.tests = MagicMock()
    svc.subject_memberships = MagicMock()
    svc.workspaces = MagicMock()
    svc.engine = MagicMock()
    svc.storage = MagicMock()
    from service.proctoring_risk_service import ProctoringRiskService

    svc.risk = ProctoringRiskService()
    return svc


def test_derive_not_started():
    from service.proctoring_service import ProctoringService

    assert (
        ProctoringService.derive_monitoring_state(attempt=None, session=None)
        == "NOT_STARTED"
    )


def test_derive_in_progress_active_session():
    from service.proctoring_service import ProctoringService

    attempt = SimpleNamespace(status="IN_PROGRESS", submission_source=None)
    session = SimpleNamespace(status="ACTIVE")
    assert (
        ProctoringService.derive_monitoring_state(attempt=attempt, session=session)
        == "IN_PROGRESS"
    )


def test_derive_submitted_student():
    from service.proctoring_service import ProctoringService

    attempt = SimpleNamespace(status="SUBMITTED", submission_source="STUDENT")
    assert (
        ProctoringService.derive_monitoring_state(attempt=attempt, session=None)
        == "SUBMITTED"
    )


def test_derive_timed_out():
    from service.proctoring_service import ProctoringService

    attempt = SimpleNamespace(status="SUBMITTED", submission_source="TIMEOUT")
    assert (
        ProctoringService.derive_monitoring_state(attempt=attempt, session=None)
        == "TIMED_OUT"
    )


def test_derive_proctoring_auto_terminated():
    from service.proctoring_service import ProctoringService

    attempt = SimpleNamespace(status="SUBMITTED", submission_source="PROCTORING_AUTO")
    assert (
        ProctoringService.derive_monitoring_state(attempt=attempt, session=None)
        == "PROCTORING_AUTO_TERMINATED"
    )


def test_derive_force_submitted():
    from service.proctoring_service import ProctoringService

    attempt = SimpleNamespace(status="SUBMITTED", submission_source="FORCE")
    assert (
        ProctoringService.derive_monitoring_state(attempt=attempt, session=None)
        == "FORCE_SUBMITTED"
    )


def test_derive_terminated_session():
    from service.proctoring_service import ProctoringService

    attempt = SimpleNamespace(status="IN_PROGRESS", submission_source=None)
    session = SimpleNamespace(status="TERMINATED")
    assert (
        ProctoringService.derive_monitoring_state(attempt=attempt, session=session)
        == "TERMINATED"
    )


def test_derive_completed_graded():
    from service.proctoring_service import ProctoringService

    attempt = SimpleNamespace(status="GRADED", submission_source="STUDENT")
    assert (
        ProctoringService.derive_monitoring_state(attempt=attempt, session=None)
        == "COMPLETED"
    )


def test_effective_score_excludes_dismissed_matches_risk_service():
    from service.proctoring_risk_service import ProctoringRiskService
    from service.proctoring_service import ProctoringService

    svc = _svc()
    attempt = SimpleNamespace(
        id=1,
        status="IN_PROGRESS",
        submission_source=None,
        last_activity_at=None,
        raw_score=80,
        final_score=None,
    )
    session = SimpleNamespace(id=9, status="ACTIVE")
    violations = [
        SimpleNamespace(score_contribution=10, status="OPEN", severity="LOW"),
        SimpleNamespace(score_contribution=20, status="DISMISSED", severity="MEDIUM"),
        SimpleNamespace(score_contribution=5, status="CONFIRMED", severity="LOW"),
    ]
    test = SimpleNamespace(id=42, name="Midterm")
    row = svc._serialize_monitoring_student_row(
        membership_id=15,
        full_name="Student",
        attempt=attempt,
        session=session,
        violations=violations,
        event_count=3,
        question_count=10,
        test=test,
    )
    expected = ProctoringRiskService().calculate(
        attempt=attempt,
        test=test,
        violations=violations,
        question_count=10,
    )
    assert row["effective_violation_score"] == expected["effective_violation_score"]
    assert row["risk_percentage"] == expected["proctoring_risk_percentage"]
    assert row["effective_violation_score"] == 15
    assert row["monitoring_state"] == "IN_PROGRESS"


def test_get_test_monitoring_includes_not_started_and_forbids_unauthorized():
    from service.exceptions import ForbiddenError
    from utils.messages import Messages

    svc = _svc()
    test = SimpleNamespace(id=42, name="Midterm", subject_id=3, created_by_membership_id=7)
    actor = SimpleNamespace(id=99, role="TEACHER")
    svc._get_test_in_workspace = MagicMock(return_value=test)
    svc.assignments.list_for_test_with_student_profile.return_value = [
        {
            "membership": SimpleNamespace(id=16),
            "user": SimpleNamespace(full_name="Another Student"),
        }
    ]
    svc.attempts.map_relevant_attempts_for_monitoring.return_value = {}
    svc.sessions.map_by_attempt_ids.return_value = {}
    svc.violations.map_for_sessions.return_value = {}
    svc.events.count_for_sessions.return_value = {}
    svc.test_questions.list_active_for_test.return_value = []

    with patch.object(svc, "_ensure_proctor_access"):
        payload = svc.get_test_monitoring(
            test_id=42, workspace_id=1, actor_membership=actor
        )
    assert payload["monitoring"]["total_assigned_students"] == 1
    assert payload["monitoring"]["not_started"] == 1
    assert payload["students"][0]["monitoring_state"] == "NOT_STARTED"
    assert payload["students"][0]["attempt_id"] is None

    with patch.object(
        svc,
        "_ensure_proctor_access",
        side_effect=ForbiddenError(Messages.INSUFFICIENT_PERMISSIONS_FOR_PROCTORING_ACCESS),
    ):
        try:
            svc.get_test_monitoring(test_id=42, workspace_id=1, actor_membership=actor)
            assert False, "expected ForbiddenError"
        except ForbiddenError as exc:
            assert Messages.INSUFFICIENT_PERMISSIONS_FOR_PROCTORING_ACCESS in str(exc)


def test_list_events_requires_proctor_access():
    from service.exceptions import ForbiddenError
    from utils.messages import Messages

    svc = _svc()
    attempt = SimpleNamespace(id=101, student_membership_id=15)
    test = SimpleNamespace(id=42, subject_id=3, created_by_membership_id=7)
    svc._resolve_attempt_view = MagicMock(return_value=(attempt, test))
    with patch.object(
        svc,
        "_ensure_proctor_access",
        side_effect=ForbiddenError(Messages.INSUFFICIENT_PERMISSIONS_FOR_PROCTORING_ACCESS),
    ):
        try:
            svc.list_events_for_attempt(
                test_id=42,
                attempt_id=101,
                workspace_id=1,
                actor_membership=SimpleNamespace(id=20),
            )
            assert False, "expected ForbiddenError"
        except ForbiddenError as exc:
            assert Messages.INSUFFICIENT_PERMISSIONS_FOR_PROCTORING_ACCESS in str(exc)


def test_teacher_monitor_broadcast_registry():
    from router.proctoring_ws import (
        broadcast_teacher_monitor,
        subscribe_teacher_monitor,
        unsubscribe_teacher_monitor,
    )

    class FakeWs:
        def __init__(self):
            self.messages = []

        def send(self, payload):
            self.messages.append(payload)

    ws = FakeWs()
    subscribe_teacher_monitor(42, ws)
    broadcast_teacher_monitor(
        42,
        {"type": "student_row_updated", "student_membership_id": 15, "changes": {}},
    )
    assert len(ws.messages) == 1
    unsubscribe_teacher_monitor(42, ws)
    broadcast_teacher_monitor(42, {"type": "student_row_updated"})
    assert len(ws.messages) == 1


def test_map_relevant_attempts_prefers_in_progress():
    from repositories.attempt_repository import TestAttemptRepository

    repo = object.__new__(TestAttemptRepository)
    older = SimpleNamespace(
        id=1, student_membership_id=10, status="SUBMITTED", started_at="2026-01-01"
    )
    active = SimpleNamespace(
        id=2, student_membership_id=10, status="IN_PROGRESS", started_at="2026-01-02"
    )
    other = SimpleNamespace(
        id=3, student_membership_id=11, status="GRADED", started_at="2026-01-03"
    )
    repo.list_for_test = MagicMock(return_value=[older, active, other])
    mapped = repo.map_relevant_attempts_for_monitoring(5)
    assert mapped[10].id == 2
    assert mapped[11].id == 3


def test_review_violation_broadcasts_student_row_updated_after_commit():
    """Dismiss/review must refresh teacher monitoring risk fields via existing helper."""
    from utils.messages import Messages

    svc = _svc()
    attempt = SimpleNamespace(id=101, student_membership_id=15)
    test = SimpleNamespace(id=42)
    session = SimpleNamespace(id=88)
    violation = SimpleNamespace(
        id=22,
        status="OPEN",
        review_notes=None,
        reviewed_by_membership_id=None,
        reviewed_at=None,
    )
    actor = SimpleNamespace(id=7)

    svc._resolve_attempt_view = MagicMock(return_value=(attempt, test))
    svc._ensure_proctor_access = MagicMock()
    svc.sessions.get_by_attempt_id.return_value = session
    svc.violations.get_for_session.return_value = violation
    svc._record_audit = MagicMock()
    svc.serialize_violation = MagicMock(return_value={"id": 22, "status": "DISMISSED"})
    svc._broadcast_session_monitoring_update = MagicMock()

    with patch("service.proctoring_service.db") as db:
        result = svc.review_violation(
            test_id=42,
            attempt_id=101,
            violation_id=22,
            workspace_id=1,
            actor_membership=actor,
            actor_user_id=9,
            status="DISMISSED",
            review_notes="false positive",
        )

    db.session.commit.assert_called_once()
    svc._broadcast_session_monitoring_update.assert_called_once_with(session)
    assert result["message"] == Messages.VIOLATION_REVIEWED
    assert violation.status == "DISMISSED"


if __name__ == "__main__":
    test_derive_not_started()
    test_derive_in_progress_active_session()
    test_derive_submitted_student()
    test_derive_timed_out()
    test_derive_force_submitted()
    test_derive_proctoring_auto_terminated()
    test_derive_terminated_session()
    test_derive_completed_graded()
    test_effective_score_excludes_dismissed_matches_risk_service()
    test_get_test_monitoring_includes_not_started_and_forbids_unauthorized()
    test_list_events_requires_proctor_access()
    test_teacher_monitor_broadcast_registry()
    test_map_relevant_attempts_prefers_in_progress()
    test_review_violation_broadcasts_student_row_updated_after_commit()
    print("all teacher monitoring checks passed")
