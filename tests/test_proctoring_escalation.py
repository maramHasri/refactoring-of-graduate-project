"""Progressive proctoring warnings and auto-termination policy.

Run: python tests/test_proctoring_escalation.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _violation(
    *,
    score: int,
    status: str = "OPEN",
    created_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        score_contribution=score,
        status=status,
        created_at=created_at or datetime.now(timezone.utc),
        severity="HIGH",
    )


def _warning_event(at: datetime | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        event_type="WARNING_GENERATED",
        occurred_at=at or datetime.now(timezone.utc),
        payload={},
    )


def test_single_low_violation_no_warning_no_terminate():
    from service.proctoring_escalation import evaluate_escalation

    decision = evaluate_escalation(
        effective_violation_score=5,
        risk_percentage=2.5,
        violations=[_violation(score=5)],
        session_events=[],
    )
    assert decision.should_warn is False
    assert decision.should_terminate is False


def test_single_high_violation_may_warn_but_never_terminate():
    from service.proctoring_escalation import (
        WARNING_SCORE_THRESHOLD,
        evaluate_escalation,
    )

    decision = evaluate_escalation(
        effective_violation_score=30,
        risk_percentage=15.0,
        violations=[_violation(score=30)],
        session_events=[],
    )
    assert 30 >= WARNING_SCORE_THRESHOLD
    assert decision.should_warn is True
    assert decision.should_terminate is False


def test_warning_only_once():
    from service.proctoring_escalation import evaluate_escalation

    decision = evaluate_escalation(
        effective_violation_score=30,
        risk_percentage=15.0,
        violations=[_violation(score=30)],
        session_events=[_warning_event()],
    )
    assert decision.should_warn is False
    assert decision.should_terminate is False


def test_score_50_without_prior_warning_does_not_terminate():
    from service.proctoring_escalation import evaluate_escalation

    decision = evaluate_escalation(
        effective_violation_score=50,
        risk_percentage=25.0,
        violations=[_violation(score=30), _violation(score=20)],
        session_events=[],
    )
    assert decision.should_warn is True
    assert decision.should_terminate is False


def test_termination_requires_warning_and_continued_violations():
    from service.proctoring_escalation import evaluate_escalation

    t0 = datetime.now(timezone.utc) - timedelta(minutes=5)
    t_warn = datetime.now(timezone.utc) - timedelta(minutes=2)
    t1 = datetime.now(timezone.utc) - timedelta(minutes=1)

    decision = evaluate_escalation(
        effective_violation_score=55,
        risk_percentage=27.5,
        violations=[
            _violation(score=30, created_at=t0),
            _violation(score=25, created_at=t1),
        ],
        session_events=[_warning_event(at=t_warn)],
    )
    assert decision.should_warn is False
    assert decision.should_terminate is True
    assert decision.violations_after_warning == 1


def test_dismissed_violations_do_not_count_toward_open_or_persistence():
    from service.proctoring_escalation import evaluate_escalation
    from service.proctoring_risk_service import ProctoringRiskService

    t_warn = datetime.now(timezone.utc) - timedelta(minutes=2)
    t_after = datetime.now(timezone.utc) - timedelta(minutes=1)
    violations = [
        _violation(score=30, created_at=t_warn - timedelta(minutes=1)),
        _violation(score=25, status="DISMISSED", created_at=t_after),
        _violation(score=20, created_at=t_after),
    ]
    effective = ProctoringRiskService()._effective_violation_score(violations)
    assert effective == 50

    decision = evaluate_escalation(
        effective_violation_score=effective,
        risk_percentage=25.0,
        violations=violations,
        session_events=[_warning_event(at=t_warn)],
    )
    # One open violation after warning + one open before → 2 open, 1 after warning
    assert decision.open_violations_count == 2
    assert decision.violations_after_warning == 1
    assert decision.should_terminate is True


def test_dismissed_only_effective_score_blocks_termination():
    from service.proctoring_escalation import evaluate_escalation
    from service.proctoring_risk_service import ProctoringRiskService

    t_warn = datetime.now(timezone.utc) - timedelta(minutes=2)
    violations = [
        _violation(score=30, status="DISMISSED"),
        _violation(score=25, status="DISMISSED"),
    ]
    effective = ProctoringRiskService()._effective_violation_score(violations)
    assert effective == 0
    decision = evaluate_escalation(
        effective_violation_score=effective,
        risk_percentage=0.0,
        violations=violations,
        session_events=[_warning_event(at=t_warn)],
    )
    assert decision.should_terminate is False
    assert decision.should_warn is False


def test_monitoring_state_proctoring_auto():
    from service.proctoring_service import ProctoringService

    attempt = SimpleNamespace(
        status="SUBMITTED", submission_source="PROCTORING_AUTO"
    )
    assert (
        ProctoringService.derive_monitoring_state(attempt=attempt, session=None)
        == "PROCTORING_AUTO_TERMINATED"
    )


def test_monitoring_row_includes_termination_reason():
    from service.proctoring_service import ProctoringService

    svc = object.__new__(ProctoringService)
    svc.risk = MagicMock()
    svc.risk.calculate.return_value = {
        "proctoring_risk_percentage": 10.0,
        "effective_violation_score": 20,
    }
    attempt = SimpleNamespace(
        id=9,
        status="SUBMITTED",
        submission_source="PROCTORING_AUTO",
        termination_reason="PROCTORING_THRESHOLD_EXCEEDED",
        last_activity_at=None,
    )
    row = ProctoringService._serialize_monitoring_student_row(
        svc,
        membership_id=1,
        full_name="Ada",
        attempt=attempt,
        session=None,
        violations=[],
        event_count=0,
        question_count=10,
        test=SimpleNamespace(id=1),
    )
    assert row["submission_source"] == "PROCTORING_AUTO"
    assert row["termination_reason"] == "PROCTORING_THRESHOLD_EXCEEDED"
    assert row["monitoring_state"] == "PROCTORING_AUTO_TERMINATED"


def test_force_remains_distinct_from_proctoring_auto():
    from service.proctoring_service import ProctoringService
    from utils.enums import AttemptSubmissionSource

    assert AttemptSubmissionSource.FORCE.value == "FORCE"
    assert AttemptSubmissionSource.PROCTORING_AUTO.value == "PROCTORING_AUTO"
    force = SimpleNamespace(status="SUBMITTED", submission_source="FORCE")
    auto = SimpleNamespace(status="SUBMITTED", submission_source="PROCTORING_AUTO")
    assert (
        ProctoringService.derive_monitoring_state(attempt=force, session=None)
        == "FORCE_SUBMITTED"
    )
    assert (
        ProctoringService.derive_monitoring_state(attempt=auto, session=None)
        == "PROCTORING_AUTO_TERMINATED"
    )


def test_ws_response_types_priority():
    from service.proctoring_service import ProctoringService

    svc = object.__new__(ProctoringService)
    svc.ingest_event_for_attempt = MagicMock(
        return_value={
            "event": {"event_type": "COPY_PASTE"},
            "violation": {"id": 1},
            "warning": {"level": "WARNING"},
            "terminated": True,
            "attempt": {"submission_source": "PROCTORING_AUTO"},
        }
    )
    with patch.object(
        ProctoringService,
        "start_session",
        MagicMock(),
    ):
        response = ProctoringService.handle_websocket_message(
            svc,
            test_id=1,
            attempt_id=2,
            workspace_id=3,
            actor_membership=SimpleNamespace(id=4),
            actor_user_id=5,
            message={"type": "copy_paste", "payload": {}},
        )
    assert response["type"] == "attempt_terminated"
    assert response["payload"]["terminated"] is True


def test_finalize_for_proctoring_auto_skips_when_not_in_progress():
    from service.attempt_service import AttemptService
    from utils.enums import TestAttemptStatus

    svc = object.__new__(AttemptService)
    attempt = SimpleNamespace(
        id=1, status=TestAttemptStatus.SUBMITTED.value, test=None, test_id=1
    )
    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = attempt

    with patch("service.attempt_service.db") as mock_db:
        mock_db.session.execute.return_value = fake_result
        mock_db.select.return_value = MagicMock()
        out = AttemptService.finalize_for_proctoring_auto(svc, attempt_id=1)
    assert out is None


def test_thresholds_require_accumulation_beyond_single_high():
    from service.proctoring_escalation import (
        TERMINATION_SCORE_THRESHOLD,
        WARNING_SCORE_THRESHOLD,
    )

    # Documented product rule: one HIGH (e.g. MULTIPLE_FACES=30) must not terminate.
    assert TERMINATION_SCORE_THRESHOLD > 30
    assert WARNING_SCORE_THRESHOLD <= 30
    assert TERMINATION_SCORE_THRESHOLD > WARNING_SCORE_THRESHOLD


if __name__ == "__main__":
    tests = [name for name, obj in list(globals().items()) if name.startswith("test_")]
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
