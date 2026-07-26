"""
Progressive proctoring escalation policy.

Consumes existing ProctoringRiskService metrics and violation history.
Does not duplicate score_contribution / risk formulas.

Threshold rationale (based on existing engine weights):
- Max single-violation contribution is MULTIPLE_FACES = 30.
- WARNING_SCORE_THRESHOLD = 25 → meaningful suspicion (e.g. HIGH tab or
  MULTIPLE_FACES), but never terminates alone.
- TERMINATION_SCORE_THRESHOLD = 50 → requires accumulated weight beyond any
  single violation (e.g. 30+20, or 25+15+12).
- MIN_OPEN_VIOLATIONS_FOR_TERMINATION = 2 → one isolated violation never ends
  an attempt.
- MIN_WARNINGS_BEFORE_TERMINATION = 1 and at least one non-dismissed violation
  after the latest warning → persistence after warning.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from models import ProctoringEvent, ProctoringViolation
from utils.enums import (
    ProctoringEventType,
    ProctoringViolationStatus,
)

# Escalation thresholds (module-level, single place).
WARNING_SCORE_THRESHOLD = 25
TERMINATION_SCORE_THRESHOLD = 50
MIN_OPEN_VIOLATIONS_FOR_TERMINATION = 2
MIN_WARNINGS_BEFORE_TERMINATION = 1
MIN_VIOLATIONS_AFTER_WARNING = 1


@dataclass
class EscalationDecision:
    should_warn: bool
    should_terminate: bool
    effective_violation_score: int
    risk_percentage: float
    open_violations_count: int
    warning_count: int
    violations_after_warning: int


def _non_dismissed(violations: list[ProctoringViolation]) -> list[ProctoringViolation]:
    return [
        v
        for v in violations
        if v.status != ProctoringViolationStatus.DISMISSED.value
    ]


def _warning_events(events: list[ProctoringEvent]) -> list[ProctoringEvent]:
    return [
        e
        for e in events
        if (e.event_type or "").upper() == ProctoringEventType.WARNING_GENERATED.value
    ]


def evaluate_escalation(
    *,
    effective_violation_score: int,
    risk_percentage: float,
    violations: list[ProctoringViolation],
    session_events: list[ProctoringEvent],
) -> EscalationDecision:
    """
    Decide warning / automatic termination from existing risk metrics + history.

    ``effective_violation_score`` must come from ProctoringRiskService.calculate.
    """
    open_violations = _non_dismissed(violations)
    warnings = _warning_events(session_events)
    warning_count = len(warnings)

    last_warning_at: datetime | None = None
    if warnings:
        last_warning_at = max(w.occurred_at for w in warnings if w.occurred_at)

    violations_after_warning = 0
    if last_warning_at is not None:
        violations_after_warning = sum(
            1
            for v in open_violations
            if v.created_at is not None and v.created_at > last_warning_at
        )

    should_warn = (
        effective_violation_score >= WARNING_SCORE_THRESHOLD
        and warning_count == 0
        and len(open_violations) >= 1
    )

    should_terminate = (
        effective_violation_score >= TERMINATION_SCORE_THRESHOLD
        and len(open_violations) >= MIN_OPEN_VIOLATIONS_FOR_TERMINATION
        and warning_count >= MIN_WARNINGS_BEFORE_TERMINATION
        and violations_after_warning >= MIN_VIOLATIONS_AFTER_WARNING
    )

    return EscalationDecision(
        should_warn=should_warn,
        should_terminate=should_terminate,
        effective_violation_score=int(effective_violation_score),
        risk_percentage=float(risk_percentage),
        open_violations_count=len(open_violations),
        warning_count=warning_count,
        violations_after_warning=violations_after_warning,
    )
