"""Unit checks for unified proctoring integrity report.

Run: python tests/test_proctoring_report.py
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


def _svc():
    from service.proctoring_service import ProctoringService
    from service.proctoring_risk_service import ProctoringRiskService

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
    svc.risk = ProctoringRiskService()
    return svc


def test_report_rejects_in_progress_attempt():
    from service.exceptions import ValidationError
    from service.proctoring_service import ProctoringService

    svc = _svc()
    now = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    attempt = SimpleNamespace(
        id=10,
        status="IN_PROGRESS",
        student_membership_id=5,
        user=SimpleNamespace(full_name="Student"),
    )
    test = SimpleNamespace(id=1, name="Exam", subject_id=2)
    svc._resolve_attempt_view = MagicMock(return_value=(attempt, test))
    svc._ensure_proctor_access = MagicMock()

    try:
        svc.get_proctoring_report(
            test_id=1,
            attempt_id=10,
            workspace_id=1,
            actor_membership=SimpleNamespace(id=99),
        )
        raise AssertionError("expected ValidationError")
    except ValidationError:
        pass
    svc.sessions.get_by_attempt_id.assert_not_called()


def test_report_requires_proctor_access_even_for_owner_student():
    """Students who own the attempt must still be blocked by _ensure_proctor_access."""
    from service.exceptions import ForbiddenError
    from utils.messages import Messages

    svc = _svc()
    attempt = SimpleNamespace(id=10, status="SUBMITTED", student_membership_id=5)
    test = SimpleNamespace(id=1, name="Exam", subject_id=2)
    actor = SimpleNamespace(id=5)
    svc._resolve_attempt_view = MagicMock(return_value=(attempt, test))

    def deny(*_a, **_k):
        raise ForbiddenError(Messages.INSUFFICIENT_PERMISSIONS_FOR_PROCTORING_ACCESS)

    svc._ensure_proctor_access = MagicMock(side_effect=deny)

    try:
        svc.get_proctoring_report(
            test_id=1,
            attempt_id=10,
            workspace_id=1,
            actor_membership=actor,
        )
        raise AssertionError("expected ForbiddenError")
    except ForbiddenError:
        pass


def test_get_proctoring_report_payload_shape():
    svc = _svc()
    now = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    evidence = SimpleNamespace(
        created_at=now,
        device_metadata={"os": "Win"},
        browser_metadata={"name": "Chrome"},
        network_metadata=None,
        screenshots=[{"ref": "s1"}],
        video_clip_ref=None,
        timeline_before=[],
        timeline_after=[],
        event_logs=[],
    )
    violation = SimpleNamespace(
        id=7,
        violation_type="TAB_SWITCH",
        severity="MEDIUM",
        score_contribution=15,
        status="OPEN",
        description="Left the exam tab",
        created_at=now,
        evidence_package=evidence,
    )
    session = SimpleNamespace(
        id=3,
        status="TERMINATED",
        started_at=now,
        ended_at=now,
        violation_score=15,
        tab_switch_count=2,
        device_metadata={"os": "Win"},
        browser_metadata={"name": "Chrome"},
        settings_snapshot={"enabled": True},
    )
    attempt = SimpleNamespace(
        id=10,
        status="SUBMITTED",
        student_membership_id=5,
        submission_source="PROCTORING_AUTO",
        started_at=now,
        submitted_at=now,
        termination_reason="PROCTORING_THRESHOLD_EXCEEDED",
        raw_score=80,
        user=SimpleNamespace(full_name="Ahmed Ali"),
    )
    test = SimpleNamespace(id=51, name="Midterm", subject_id=2)

    svc._resolve_attempt_view = MagicMock(return_value=(attempt, test))
    svc._ensure_proctor_access = MagicMock()
    svc.sessions.get_by_attempt_id.return_value = session
    svc.violations.list_for_session.return_value = [violation]
    svc.events.list_for_session.return_value = [
        SimpleNamespace(
            event_type="TAB_SWITCH",
            occurred_at=now,
            source="WEBSOCKET",
            payload={"count": 1},
        )
    ]
    svc.test_questions.list_active_for_test.return_value = [object()] * 10

    report = svc.get_proctoring_report(
        test_id=51,
        attempt_id=10,
        workspace_id=1,
        actor_membership=SimpleNamespace(id=99),
    )

    assert report["attempt"]["attempt_id"] == 10
    assert report["attempt"]["student_id"] == 5
    assert report["attempt"]["student_name"] == "Ahmed Ali"
    assert report["attempt"]["test_title"] == "Midterm"
    assert report["attempt"]["submission_source"] == "PROCTORING_AUTO"
    assert report["attempt"]["termination_reason"] == "PROCTORING_THRESHOLD_EXCEEDED"

    assert report["proctoring_summary"]["session_status"] == "TERMINATED"
    assert report["proctoring_summary"]["total_violations"] == 1
    assert report["proctoring_summary"]["medium_severity_count"] == 1

    assert report["session"]["session_id"] == 3
    assert report["session"]["tab_switch_count"] == 2
    assert "device_metadata" in report["session"]["metadata"]

    assert len(report["violations"]) == 1
    assert report["violations"][0]["type"] == "TAB_SWITCH"
    assert report["violations"][0]["evidence_available"] is True

    assert len(report["events_timeline"]) == 1
    assert report["events_timeline"][0]["source"] == "WEBSOCKET"

    assert len(report["evidence_packages"]) == 1
    assert report["evidence_packages"][0]["evidence_type"] == "SCREENSHOT"
    assert report["evidence_packages"][0]["violation_id"] == 7

    assert report["recommendation"]["status"] == "SUSPICIOUS"


def test_recommendation_safe_when_no_violations():
    from service.proctoring_service import ProctoringService

    attempt = SimpleNamespace(submission_source="STUDENT", termination_reason=None)
    risk = {
        "effective_violation_score": 0,
        "high_severity_count": 0,
        "violations_count": 0,
    }
    rec = ProctoringService._build_report_recommendation(attempt=attempt, risk=risk)
    assert rec["status"] == "SAFE"


def test_recommendation_needs_review_on_warning_threshold():
    from service.proctoring_service import ProctoringService

    attempt = SimpleNamespace(submission_source="STUDENT", termination_reason=None)
    risk = {
        "effective_violation_score": 25,
        "high_severity_count": 0,
        "violations_count": 2,
    }
    rec = ProctoringService._build_report_recommendation(attempt=attempt, risk=risk)
    assert rec["status"] == "NEEDS_REVIEW"


if __name__ == "__main__":
    tests = [
        test_report_rejects_in_progress_attempt,
        test_report_requires_proctor_access_even_for_owner_student,
        test_get_proctoring_report_payload_shape,
        test_recommendation_safe_when_no_violations,
        test_recommendation_needs_review_on_warning_threshold,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"OK  {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"\n{len(tests) - failed} passed" if not failed else f"\n{failed} failed")
    raise SystemExit(failed)
