"""
Proctoring risk calculation — converts violation data into a risk percentage.

This service does not mutate attempts, scores, sessions, or violations.
"""

from __future__ import annotations

from models import ProctoringViolation, Test, TestAttempt
from utils.enums import ProctoringViolationStatus, ViolationSeverity


class ProctoringRiskService:
    QUESTION_BASELINE = 50
    QUESTION_FACTOR_MIN = 0.5
    QUESTION_FACTOR_MAX = 2.0
    RISK_NORMALIZATION = 100
    MAX_RISK_PERCENTAGE = 50

    def requires_teacher_approval(self, test: Test, attempt: TestAttempt) -> bool:
        """True when proctoring is enabled and the attempt has a proctoring session."""
        from service.proctoring_service import ProctoringService

        if not ProctoringService().is_proctoring_enabled(test):
            return False
        return attempt.proctoring_session is not None

    def calculate(
        self,
        *,
        attempt: TestAttempt,
        test: Test,
        violations: list[ProctoringViolation],
        question_count: int,
    ) -> dict:
        effective_violation_score = self._effective_violation_score(violations)
        question_factor = self._question_factor(question_count)
        risk_percentage = self._risk_percentage(
            effective_violation_score, question_factor
        )
        raw_score = float(attempt.raw_score or 0)
        penalty = round(raw_score * (risk_percentage / 100), 2)
        suggested_final_score = round(max(0.0, raw_score - penalty), 2)

        severity_counts = self._severity_counts(violations)

        return {
            "proctoring_risk_percentage": risk_percentage,
            "effective_violation_score": effective_violation_score,
            "violations_count": len(
                [v for v in violations if v.status != ProctoringViolationStatus.DISMISSED.value]
            ),
            "high_severity_count": severity_counts["high"],
            "medium_severity_count": severity_counts["medium"],
            "low_severity_count": severity_counts["low"],
            "question_factor": question_factor,
            "question_count": question_count,
            "penalty": penalty,
            "suggested_final_score": suggested_final_score,
        }

    def build_grading_review(
        self,
        *,
        attempt: TestAttempt,
        test: Test,
        violations: list[ProctoringViolation],
        question_count: int,
    ) -> dict:
        risk = self.calculate(
            attempt=attempt,
            test=test,
            violations=violations,
            question_count=question_count,
        )
        requires_approval = self.requires_teacher_approval(test, attempt)
        return {
            "attempt_id": attempt.id,
            "student_name": (
                attempt.user.full_name
                if attempt.user is not None and attempt.user.full_name
                else None
            ),
            "raw_score": attempt.raw_score,
            "maximum_score": None,
            "proctoring": {
                "risk_percentage": risk["proctoring_risk_percentage"],
                "effective_violation_score": risk["effective_violation_score"],
                "violations_count": risk["violations_count"],
                "high_severity_count": risk["high_severity_count"],
                "medium_severity_count": risk["medium_severity_count"],
                "low_severity_count": risk["low_severity_count"],
            },
            "penalty": risk["penalty"],
            "suggested_final_score": risk["suggested_final_score"],
            "current_final_score": attempt.final_score,
            "requires_teacher_approval": requires_approval
            and attempt.final_score is None,
        }

    def _effective_violation_score(self, violations: list[ProctoringViolation]) -> int:
        return sum(
            int(v.score_contribution or 0)
            for v in violations
            if v.status != ProctoringViolationStatus.DISMISSED.value
        )

    def _question_factor(self, question_count: int) -> float:
        if question_count <= 0:
            return self.QUESTION_FACTOR_MIN
        raw = question_count / self.QUESTION_BASELINE
        return max(self.QUESTION_FACTOR_MIN, min(self.QUESTION_FACTOR_MAX, raw))

    def _risk_percentage(
        self, effective_violation_score: int, question_factor: float
    ) -> float:
        base_risk = effective_violation_score / self.RISK_NORMALIZATION
        adjusted_risk = base_risk * question_factor
        return round(min(adjusted_risk * 100, self.MAX_RISK_PERCENTAGE), 2)

    def _severity_counts(self, violations: list[ProctoringViolation]) -> dict:
        counts = {"high": 0, "medium": 0, "low": 0}
        for violation in violations:
            if violation.status == ProctoringViolationStatus.DISMISSED.value:
                continue
            severity = (violation.severity or "").upper()
            if severity == ViolationSeverity.HIGH.value:
                counts["high"] += 1
            elif severity == ViolationSeverity.MEDIUM.value:
                counts["medium"] += 1
            elif severity == ViolationSeverity.LOW.value:
                counts["low"] += 1
        return counts
