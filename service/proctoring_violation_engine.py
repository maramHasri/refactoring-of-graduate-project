"""
Rule-based proctoring violation engine.

Each ingested event may contribute to violation scoring and trigger violations
with escalating severity (LOW → MEDIUM → HIGH).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from models import ProctoringSession
from repositories.proctoring_repository import ProctoringEventRepository
from utils.enums import (
    ProctoringEventType,
    ProctoringViolationType,
    ViolationSeverity,
)

FACE_LOST_MEDIUM_SECONDS = 10
TAB_SWITCH_MEDIUM_COUNT = 2
TAB_SWITCH_HIGH_COUNT = 5


@dataclass
class ViolationDecision:
    violation_type: str
    severity: str
    score_contribution: int
    description: str
    generate_evidence: bool


class ProctoringViolationEngine:
    def __init__(self):
        self.events = ProctoringEventRepository()

    def evaluate(
        self,
        session: ProctoringSession,
        event_type: str,
        *,
        payload: dict | None = None,
        occurred_at: datetime | None = None,
    ) -> ViolationDecision | None:
        occurred_at = occurred_at or datetime.now(timezone.utc)
        normalized = (event_type or "").upper()

        if normalized in (
            ProctoringEventType.MULTIPLE_FACES.value,
            "MULTIPLE_FACES",
        ):
            return ViolationDecision(
                violation_type=ProctoringViolationType.MULTIPLE_FACES.value,
                severity=ViolationSeverity.HIGH.value,
                score_contribution=30,
                description="Multiple faces detected in camera feed",
                generate_evidence=True,
            )

        if normalized in (
            ProctoringEventType.FACE_LOST.value,
            ProctoringEventType.NO_FACE.value,
        ):
            duration = self.events.face_lost_duration_seconds(
                session.id, now=occurred_at
            )
            if duration >= FACE_LOST_MEDIUM_SECONDS:
                return ViolationDecision(
                    violation_type=ProctoringViolationType.FACE_NOT_DETECTED.value,
                    severity=ViolationSeverity.MEDIUM.value,
                    score_contribution=15,
                    description=f"Face not detected for {int(duration)} seconds",
                    generate_evidence=True,
                )
            return ViolationDecision(
                violation_type=ProctoringViolationType.FACE_NOT_DETECTED.value,
                severity=ViolationSeverity.LOW.value,
                score_contribution=5,
                description="Face temporarily not detected",
                generate_evidence=False,
            )

        if normalized in (
            ProctoringEventType.TAB_SWITCH.value,
            ProctoringEventType.WINDOW_BLUR.value,
        ):
            count = session.tab_switch_count
            if count >= TAB_SWITCH_HIGH_COUNT:
                severity = ViolationSeverity.HIGH.value
                score = 25
                desc = f"Repeated tab/window switches ({count})"
                evidence = True
            elif count >= TAB_SWITCH_MEDIUM_COUNT:
                severity = ViolationSeverity.MEDIUM.value
                score = 12
                desc = f"Multiple tab/window switches ({count})"
                evidence = True
            else:
                severity = ViolationSeverity.LOW.value
                score = 5
                desc = "Tab or window focus lost"
                evidence = False
            return ViolationDecision(
                violation_type=ProctoringViolationType.TAB_SWITCH.value,
                severity=severity,
                score_contribution=score,
                description=desc,
                generate_evidence=evidence,
            )

        if normalized == ProctoringEventType.AUDIO_ANOMALY.value:
            return ViolationDecision(
                violation_type=ProctoringViolationType.AUDIO_ANOMALY.value,
                severity=ViolationSeverity.MEDIUM.value,
                score_contribution=10,
                description="Audio anomaly detected",
                generate_evidence=True,
            )

        if normalized == ProctoringEventType.SCREEN_INACTIVITY.value:
            return ViolationDecision(
                violation_type=ProctoringViolationType.SCREEN_INACTIVITY.value,
                severity=ViolationSeverity.LOW.value,
                score_contribution=5,
                description="Prolonged screen inactivity",
                generate_evidence=False,
            )

        if normalized == ProctoringEventType.SUSPICIOUS_NAVIGATION.value:
            return ViolationDecision(
                violation_type=ProctoringViolationType.SUSPICIOUS_NAVIGATION.value,
                severity=ViolationSeverity.MEDIUM.value,
                score_contribution=15,
                description="Suspicious navigation detected",
                generate_evidence=True,
            )

        if normalized == ProctoringEventType.FULLSCREEN_EXIT.value:
            return ViolationDecision(
                violation_type=ProctoringViolationType.FULLSCREEN_EXIT.value,
                severity=ViolationSeverity.MEDIUM.value,
                score_contribution=10,
                description="Exited fullscreen exam mode",
                generate_evidence=True,
            )

        if normalized == ProctoringEventType.COPY_PASTE.value:
            return ViolationDecision(
                violation_type=ProctoringViolationType.COPY_PASTE.value,
                severity=ViolationSeverity.HIGH.value,
                score_contribution=20,
                description="Copy/paste action detected during exam",
                generate_evidence=True,
            )

        return None

    def timeline_window(
        self, *, center: datetime, before_seconds: int = 30, after_seconds: int = 15
    ) -> tuple[datetime, datetime]:
        return (
            center - timedelta(seconds=before_seconds),
            center + timedelta(seconds=after_seconds),
        )
