"""
Proctoring orchestration — sessions, events, violations, evidence, audit.
"""

from __future__ import annotations

from utils.messages import Messages

import json
import logging
from datetime import datetime, timezone

from flask import current_app

from models import (
    ProctoringAuditLog,
    ProctoringEvent,
    ProctoringEvidencePackage,
    ProctoringSession,
    ProctoringViolation,
    Test,
    TestAttempt,
)
from repositories.attempt_repository import TestAttemptRepository
from repositories.proctoring_repository import (
    ProctoringAuditLogRepository,
    ProctoringEventRepository,
    ProctoringEvidenceRepository,
    ProctoringSessionRepository,
    ProctoringViolationRepository,
)
from repositories.subject_repository import SubjectMembershipRepository
from repositories.test_assignment_repository import TestStudentAssignmentRepository
from repositories.test_repository import TestQuestionRepository, TestRepository
from repositories.workspace_repository import WorkspaceRepository
from service.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from service.proctoring_risk_service import ProctoringRiskService
from service.proctoring_storage import ProctoringStorageService
from service.proctoring_violation_engine import ProctoringViolationEngine, ViolationDecision
from utils.academic_rbac import can_manage_test_attempts, verify_subject_student_access
from utils.db import db
from utils.enums import (
    AttemptSubmissionSource,
    AttemptTerminationReason,
    ProctoringAuditAction,
    ProctoringEventType,
    ProctoringSessionStatus,
    ProctoringViolationStatus,
    TestAttemptStatus,
    ViolationSeverity,
)

logger = logging.getLogger(__name__)

_EVIDENCE_SEVERITIES = frozenset(
    {ViolationSeverity.MEDIUM.value, ViolationSeverity.HIGH.value}
)

# Derived monitoring view states (not persisted enums).
_MONITORING_NOT_STARTED = "NOT_STARTED"
_MONITORING_IN_PROGRESS = "IN_PROGRESS"
_MONITORING_SUBMITTED = "SUBMITTED"
_MONITORING_TIMED_OUT = "TIMED_OUT"
_MONITORING_FORCE_SUBMITTED = "FORCE_SUBMITTED"
_MONITORING_PROCTORING_AUTO = "PROCTORING_AUTO_TERMINATED"
_MONITORING_TERMINATED = "TERMINATED"
_MONITORING_COMPLETED = "COMPLETED"


class ProctoringService:
    def __init__(self):
        self.sessions = ProctoringSessionRepository()
        self.events = ProctoringEventRepository()
        self.violations = ProctoringViolationRepository()
        self.evidence = ProctoringEvidenceRepository()
        self.audit_logs = ProctoringAuditLogRepository()
        self.attempts = TestAttemptRepository()
        self.test_questions = TestQuestionRepository()
        self.assignments = TestStudentAssignmentRepository()
        self.tests = TestRepository()
        self.subject_memberships = SubjectMembershipRepository()
        self.workspaces = WorkspaceRepository()
        self.engine = ProctoringViolationEngine()
        self.storage = ProctoringStorageService()
        self.risk = ProctoringRiskService()

    def is_proctoring_enabled(self, test: Test) -> bool:
        mode = (test.availability_time_mode or "").upper()
        if mode == "SURVEY":
            return False
        settings = self._load_json(test.settings_config) or {}
        proctoring = settings.get("proctoring") or {}
        return bool(proctoring.get("enabled", False))

    def ensure_session_for_attempt(
        self,
        *,
        test_attempt: TestAttempt,
        workspace_id: int,
        test: Test,
        device_metadata: dict | None = None,
        browser_metadata: dict | None = None,
    ) -> ProctoringSession | None:
        if not self.is_proctoring_enabled(test):
            return None

        existing = self.sessions.get_by_attempt_id(test_attempt.id)
        if existing:
            if existing.status == ProctoringSessionStatus.ACTIVE.value:
                return existing
            return existing

        settings = self._load_json(test.settings_config) or {}
        now = datetime.now(timezone.utc)
        session = ProctoringSession(
            test_attempt_id=test_attempt.id,
            workspace_id=workspace_id,
            status=ProctoringSessionStatus.ACTIVE.value,
            started_at=now,
            settings_snapshot=settings.get("proctoring"),
            device_metadata=device_metadata,
            browser_metadata=browser_metadata,
        )
        self.sessions.add(session)
        db.session.flush()
        self._record_audit(
            session,
            action=ProctoringAuditAction.SESSION_STARTED.value,
            actor_user_id=test_attempt.user_id,
            details={"test_attempt_id": test_attempt.id},
        )
        self.ingest_event(
            session=session,
            event_type=ProctoringEventType.SESSION_STARTED.value,
            payload={"test_attempt_id": test_attempt.id},
            source="SYSTEM",
            actor_user_id=test_attempt.user_id,
            skip_violation_check=True,
        )
        db.session.commit()
        logger.info(
            "Proctoring session started id=%s attempt_id=%s",
            session.id,
            test_attempt.id,
        )
        return session

    def start_session(
        self,
        *,
        test_id: int,
        attempt_id: int,
        workspace_id: int,
        actor_membership,
        actor_user_id: int,
        device_metadata: dict | None = None,
        browser_metadata: dict | None = None,
    ) -> dict:
        attempt, test = self._resolve_student_attempt(
            test_id, attempt_id, workspace_id, actor_membership
        )
        if attempt.status != TestAttemptStatus.IN_PROGRESS.value:
            raise ValidationError(Messages.PROCTORING_SESSION_REQUIRES_AN_IN_PROGRESS_ATTEMPT)

        session = self.ensure_session_for_attempt(
            test_attempt=attempt,
            workspace_id=workspace_id,
            test=test,
            device_metadata=device_metadata,
            browser_metadata=browser_metadata,
        )
        if not session:
            raise ValidationError(Messages.PROCTORING_IS_NOT_ENABLED_FOR_THIS_TEST)
        return {
            "message": Messages.PROCTORING_SESSION_ACTIVE,
            "session": self.serialize_session(session),
        }

    def get_session_status(
        self,
        *,
        test_id: int,
        attempt_id: int,
        workspace_id: int,
        actor_membership,
    ) -> dict:
        attempt, test = self._resolve_attempt_view(
            test_id, attempt_id, workspace_id, actor_membership
        )
        session = self.sessions.get_by_attempt_id(attempt.id)
        if not session:
            raise NotFoundError(Messages.PROCTORING_SESSION_NOT_FOUND)
        return {"session": self.serialize_session(session, include_counts=True)}

    def list_test_sessions(
        self, *, test_id: int, workspace_id: int, actor_membership
    ) -> list[dict]:
        test = self._get_test_in_workspace(test_id, workspace_id)
        self._ensure_proctor_access(test, workspace_id, actor_membership)
        rows = self.sessions.list_active_for_test(test.id, workspace_id)
        return [self.serialize_session(row, include_counts=True) for row in rows]

    def get_test_monitoring(
        self, *, test_id: int, workspace_id: int, actor_membership
    ) -> dict:
        """
        Teacher/admin snapshot: all assigned students for a test, with derived
        monitoring_state. Backend remains source of truth for live dashboards.
        """
        test = self._get_test_in_workspace(test_id, workspace_id)
        self._ensure_proctor_access(test, workspace_id, actor_membership)

        assigned = self.assignments.list_for_test_with_student_profile(test.id)
        attempts_by_student = self.attempts.map_relevant_attempts_for_monitoring(test.id)
        attempt_ids = [a.id for a in attempts_by_student.values()]
        sessions_by_attempt = self.sessions.map_by_attempt_ids(attempt_ids)
        session_ids = [s.id for s in sessions_by_attempt.values()]
        violations_by_session = self.violations.map_for_sessions(session_ids)
        event_counts = self.events.count_for_sessions(session_ids)
        question_count = len(self.test_questions.list_active_for_test(test.id))

        students: list[dict] = []
        for row in assigned:
            membership = row["membership"]
            user = row["user"]
            attempt = attempts_by_student.get(membership.id)
            session = (
                sessions_by_attempt.get(attempt.id) if attempt is not None else None
            )
            session_violations = (
                violations_by_session.get(session.id, []) if session is not None else []
            )
            students.append(
                self._serialize_monitoring_student_row(
                    membership_id=membership.id,
                    full_name=user.full_name if user else None,
                    attempt=attempt,
                    session=session,
                    violations=session_violations,
                    event_count=(
                        event_counts.get(session.id, 0) if session is not None else 0
                    ),
                    question_count=question_count,
                    test=test,
                )
            )

        return {
            "test_id": test.id,
            "name": test.name,
            "title": test.name,
            "monitoring": self._monitoring_summary(students),
            "students": students,
            "count": len(students),
        }

    def list_events_for_attempt(
        self,
        *,
        test_id: int,
        attempt_id: int,
        workspace_id: int,
        actor_membership,
        since: datetime | None = None,
        limit: int = 500,
    ) -> list[dict]:
        attempt, test = self._resolve_attempt_view(
            test_id, attempt_id, workspace_id, actor_membership
        )
        self._ensure_proctor_access(test, workspace_id, actor_membership)
        session = self.sessions.get_by_attempt_id(attempt.id)
        if not session:
            return []
        limit = max(1, min(int(limit or 500), 1000))
        rows = self.events.list_for_session(
            session.id, since=since, limit=limit, ascending=True
        )
        return [self._serialize_event(row) for row in rows]

    @staticmethod
    def derive_monitoring_state(
        *,
        attempt: TestAttempt | None,
        session: ProctoringSession | None,
    ) -> str:
        if attempt is None:
            return _MONITORING_NOT_STARTED

        if attempt.status == TestAttemptStatus.IN_PROGRESS.value:
            if (
                session is not None
                and session.status == ProctoringSessionStatus.TERMINATED.value
            ):
                return _MONITORING_TERMINATED
            return _MONITORING_IN_PROGRESS

        if attempt.status == TestAttemptStatus.SUBMITTED.value:
            source = (attempt.submission_source or "").upper()
            if source == AttemptSubmissionSource.TIMEOUT.value:
                return _MONITORING_TIMED_OUT
            if source == AttemptSubmissionSource.FORCE.value:
                return _MONITORING_FORCE_SUBMITTED
            if source == AttemptSubmissionSource.PROCTORING_AUTO.value:
                return _MONITORING_PROCTORING_AUTO
            return _MONITORING_SUBMITTED

        if attempt.status == TestAttemptStatus.GRADED.value:
            return _MONITORING_COMPLETED

        return _MONITORING_NOT_STARTED

    def build_monitoring_student_row(
        self,
        *,
        test: Test,
        membership_id: int,
        full_name: str | None,
        attempt: TestAttempt | None,
        session: ProctoringSession | None = None,
        violations: list[ProctoringViolation] | None = None,
        event_count: int | None = None,
        question_count: int | None = None,
    ) -> dict:
        if session is None and attempt is not None:
            session = self.sessions.get_by_attempt_id(attempt.id)
        if violations is None:
            violations = (
                self.violations.list_for_session(session.id) if session is not None else []
            )
        if event_count is None:
            event_count = (
                len(self.events.list_for_session(session.id, limit=1000))
                if session is not None
                else 0
            )
        if question_count is None:
            question_count = len(self.test_questions.list_active_for_test(test.id))
        return self._serialize_monitoring_student_row(
            membership_id=membership_id,
            full_name=full_name,
            attempt=attempt,
            session=session,
            violations=violations,
            event_count=event_count,
            question_count=question_count,
            test=test,
        )

    def notify_teacher_monitors(
        self,
        *,
        test_id: int,
        message_type: str,
        student_membership_id: int,
        attempt: TestAttempt | None = None,
        session: ProctoringSession | None = None,
        changes: dict | None = None,
        violation: dict | None = None,
    ) -> None:
        payload: dict = {
            "type": message_type,
            "test_id": test_id,
            "student_membership_id": student_membership_id,
            "attempt_id": attempt.id if attempt is not None else None,
        }
        if changes is not None:
            payload["changes"] = changes
        if violation is not None:
            payload["violation"] = violation
        try:
            from router.proctoring_ws import broadcast_teacher_monitor

            broadcast_teacher_monitor(test_id, payload)
        except Exception:
            logger.exception(
                "Failed to broadcast teacher monitor event test_id=%s type=%s",
                test_id,
                message_type,
            )

    def notify_monitoring_row_updated(
        self,
        *,
        test: Test,
        attempt: TestAttempt,
        session: ProctoringSession | None = None,
        violation: ProctoringViolation | None = None,
    ) -> None:
        membership = attempt.student_membership
        user = membership.user if membership else None
        full_name = user.full_name if user else None
        row = self.build_monitoring_student_row(
            test=test,
            membership_id=attempt.student_membership_id,
            full_name=full_name,
            attempt=attempt,
            session=session,
        )
        self.notify_teacher_monitors(
            test_id=test.id,
            message_type="student_row_updated",
            student_membership_id=attempt.student_membership_id,
            attempt=attempt,
            session=session,
            changes={
                "monitoring_state": row["monitoring_state"],
                "attempt_status": row["attempt_status"],
                "submission_source": row["submission_source"],
                "termination_reason": row["termination_reason"],
                "proctoring_session_id": row["proctoring_session_id"],
                "proctoring_session_status": row["proctoring_session_status"],
                "effective_violation_score": row["effective_violation_score"],
                "risk_percentage": row["risk_percentage"],
                "violation_count": row["violation_count"],
                "event_count": row["event_count"],
                "last_activity_at": row["last_activity_at"],
            },
        )
        # TEMP TRACE — remove after proctoring path diagnosis
        logger.info(
            "[BROADCAST] student_row_updated sent test_id=%s membership_id=%s violation_count=%s event_count=%s",
            test.id,
            attempt.student_membership_id,
            row["violation_count"],
            row["event_count"],
        )
        if violation is not None:
            self.notify_teacher_monitors(
                test_id=test.id,
                message_type="violation_created",
                student_membership_id=attempt.student_membership_id,
                attempt=attempt,
                session=session,
                violation={
                    "id": violation.id,
                    "violation_type": violation.violation_type,
                    "type": violation.violation_type,
                    "severity": violation.severity,
                    "status": violation.status,
                    "score_contribution": violation.score_contribution,
                },
            )
            # TEMP TRACE — remove after proctoring path diagnosis
            logger.info(
                "[BROADCAST] violation_created sent test_id=%s violation_id=%s type=%s",
                test.id,
                violation.id,
                violation.violation_type,
            )

    def _serialize_monitoring_student_row(
        self,
        *,
        membership_id: int,
        full_name: str | None,
        attempt: TestAttempt | None,
        session: ProctoringSession | None,
        violations: list[ProctoringViolation],
        event_count: int,
        question_count: int,
        test: Test,
    ) -> dict:
        monitoring_state = self.derive_monitoring_state(attempt=attempt, session=session)
        risk_percentage = 0.0
        effective_score = 0
        if attempt is not None:
            risk = self.risk.calculate(
                attempt=attempt,
                test=test,
                violations=violations,
                question_count=question_count,
            )
            risk_percentage = float(risk["proctoring_risk_percentage"])
            effective_score = int(risk["effective_violation_score"])

        return {
            "student_membership_id": membership_id,
            "full_name": full_name,
            "student_name": full_name,
            "attempt_id": attempt.id if attempt is not None else None,
            "attempt_status": attempt.status if attempt is not None else None,
            "submission_source": (
                attempt.submission_source if attempt is not None else None
            ),
            "termination_reason": (
                getattr(attempt, "termination_reason", None)
                if attempt is not None
                else None
            ),
            "proctoring_session_id": session.id if session is not None else None,
            "proctoring_session_status": session.status if session is not None else None,
            "monitoring_state": monitoring_state,
            "effective_violation_score": effective_score,
            "risk_percentage": risk_percentage,
            "violation_count": len(violations),
            "event_count": int(event_count or 0),
            "last_activity_at": (
                attempt.last_activity_at.isoformat()
                if attempt is not None and attempt.last_activity_at
                else None
            ),
        }

    @staticmethod
    def _monitoring_summary(students: list[dict]) -> dict:
        counts = {
            "total_assigned_students": len(students),
            "not_started": 0,
            "in_progress": 0,
            "submitted": 0,
            "timed_out": 0,
            "force_submitted": 0,
            "proctoring_auto_terminated": 0,
            "terminated": 0,
            "completed": 0,
        }
        for row in students:
            state = row.get("monitoring_state")
            if state == _MONITORING_NOT_STARTED:
                counts["not_started"] += 1
            elif state == _MONITORING_IN_PROGRESS:
                counts["in_progress"] += 1
            elif state == _MONITORING_SUBMITTED:
                counts["submitted"] += 1
            elif state == _MONITORING_TIMED_OUT:
                counts["timed_out"] += 1
            elif state == _MONITORING_FORCE_SUBMITTED:
                counts["force_submitted"] += 1
            elif state == _MONITORING_PROCTORING_AUTO:
                counts["proctoring_auto_terminated"] += 1
            elif state == _MONITORING_TERMINATED:
                counts["terminated"] += 1
            elif state == _MONITORING_COMPLETED:
                counts["completed"] += 1
        return counts

    def ingest_event(
        self,
        *,
        session: ProctoringSession,
        event_type: str,
        payload: dict | None = None,
        source: str = "REST",
        occurred_at: datetime | None = None,
        actor_user_id: int | None = None,
        actor_membership_id: int | None = None,
        skip_violation_check: bool = False,
    ) -> dict:
        if session.status != ProctoringSessionStatus.ACTIVE.value:
            raise ConflictError(Messages.PROCTORING_SESSION_IS_NOT_ACTIVE)

        occurred_at = occurred_at or datetime.now(timezone.utc)
        normalized = (event_type or "").upper()
        # TEMP TRACE
        print(f"[INGEST_EVENT]\nevent_type={normalized}", flush=True)
        logger.info("[INGEST_EVENT]\nevent_type=%s", normalized)

        event = ProctoringEvent(
            session_id=session.id,
            event_type=normalized,
            payload=payload or {},
            occurred_at=occurred_at,
            source=source,
        )
        self.events.add(event)

        if normalized in (
            ProctoringEventType.TAB_SWITCH.value,
            ProctoringEventType.WINDOW_BLUR.value,
        ):
            session.tab_switch_count = (session.tab_switch_count or 0) + 1

        self._record_audit(
            session,
            action=ProctoringAuditAction.EVENT_INGESTED.value,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            details={"event_type": normalized, "source": source},
        )

        result = {
            "event": self._serialize_event(event),
            "violation": None,
            "warning": None,
            "terminated": False,
            "attempt": None,
        }
        created_violation = None
        should_terminate = False

        if not skip_violation_check:
            # TEMP TRACE
            print(f"[BEFORE EVALUATE]\nevent_type={normalized}", flush=True)
            logger.info("[BEFORE EVALUATE]\nevent_type=%s", normalized)
            decision = self.engine.evaluate(
                session, normalized, payload=payload, occurred_at=occurred_at
            )
            # TEMP TRACE
            if decision is None:
                print("[AFTER EVALUATE]\nNO VIOLATION", flush=True)
                logger.info("[AFTER EVALUATE]\nNO VIOLATION")
            else:
                print(
                    f"[AFTER EVALUATE]\nVIOLATION CREATED\ndecision={decision}",
                    flush=True,
                )
                logger.info(
                    "[AFTER EVALUATE]\nVIOLATION CREATED\ndecision=%s",
                    {
                        "violation_type": decision.violation_type,
                        "severity": decision.severity,
                        "score_contribution": decision.score_contribution,
                    },
                )
            if decision:
                created_violation = self._create_violation(
                    session,
                    decision,
                    trigger_event=event,
                    payload=payload,
                )
                result["violation"] = self.serialize_violation(created_violation)
                if decision.severity in _EVIDENCE_SEVERITIES:
                    result["evidence"] = self.serialize_evidence(
                        created_violation.evidence_package
                    )

        if created_violation is not None:
            db.session.flush()
            should_terminate = self._apply_progressive_escalation(
                session,
                result=result,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
            )

        db.session.commit()

        if should_terminate:
            from service.attempt_service import AttemptService

            finalized = AttemptService().finalize_for_proctoring_auto(
                attempt_id=session.test_attempt_id,
                termination_reason=AttemptTerminationReason.PROCTORING_THRESHOLD_EXCEEDED.value,
            )
            if finalized:
                result["terminated"] = True
                result["attempt"] = finalized["attempt"]
            # finalize_for_proctoring_auto already notifies teacher monitoring
        else:
            self._broadcast_session_monitoring_update(
                session, violation=created_violation
            )
        return result

    def _apply_progressive_escalation(
        self,
        session: ProctoringSession,
        *,
        result: dict,
        actor_user_id: int | None = None,
        actor_membership_id: int | None = None,
    ) -> bool:
        """
        Progressive warning / auto-termination after a new violation.

        Returns True when automatic termination should run after commit.
        """
        from service.proctoring_escalation import evaluate_escalation

        locked = db.session.execute(
            db.select(ProctoringSession)
            .where(ProctoringSession.id == session.id)
            .with_for_update()
        ).scalar_one_or_none()
        if not locked or locked.status != ProctoringSessionStatus.ACTIVE.value:
            return False

        attempt = locked.test_attempt or self.attempts.get_by_id(locked.test_attempt_id)
        if not attempt or attempt.status != TestAttemptStatus.IN_PROGRESS.value:
            return False

        test = attempt.test or self.tests.get_by_id(attempt.test_id)
        if not test:
            return False

        violations = self.violations.list_for_session(locked.id)
        events = self.events.list_for_session(locked.id, limit=1000)
        question_count = len(self.test_questions.list_active_for_test(test.id))
        risk = self.risk.calculate(
            attempt=attempt,
            test=test,
            violations=violations,
            question_count=question_count,
        )
        decision = evaluate_escalation(
            effective_violation_score=int(risk["effective_violation_score"]),
            risk_percentage=float(risk["proctoring_risk_percentage"]),
            violations=violations,
            session_events=events,
        )

        if decision.should_warn:
            warning = self._emit_warning(
                locked,
                effective_violation_score=decision.effective_violation_score,
                risk_percentage=decision.risk_percentage,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
            )
            result["warning"] = warning
            db.session.flush()

        if decision.should_terminate:
            self._record_audit(
                locked,
                action=ProctoringAuditAction.SESSION_TERMINATED.value,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                details={
                    "automatic": True,
                    "submission_source": AttemptSubmissionSource.PROCTORING_AUTO.value,
                    "termination_reason": (
                        AttemptTerminationReason.PROCTORING_THRESHOLD_EXCEEDED.value
                    ),
                    "effective_violation_score": decision.effective_violation_score,
                    "risk_percentage": decision.risk_percentage,
                    "open_violations_count": decision.open_violations_count,
                    "warning_count": decision.warning_count,
                    "violations_after_warning": decision.violations_after_warning,
                },
            )
            return True
        return False

    def _emit_warning(
        self,
        session: ProctoringSession,
        *,
        effective_violation_score: int,
        risk_percentage: float,
        actor_user_id: int | None = None,
        actor_membership_id: int | None = None,
    ) -> dict:
        """Persist WARNING_GENERATED event + audit (idempotent per session)."""
        existing = [
            e
            for e in self.events.list_for_session(session.id, limit=1000)
            if (e.event_type or "").upper()
            == ProctoringEventType.WARNING_GENERATED.value
        ]
        if existing:
            payload = existing[-1].payload or {}
            return {
                "level": payload.get("level") or "WARNING",
                "message": payload.get("message")
                or Messages.PROCTORING_WARNING_SUSPICIOUS_ACTIVITY,
                "effective_violation_score": effective_violation_score,
                "risk_percentage": risk_percentage,
            }

        now = datetime.now(timezone.utc)
        warning_payload = {
            "level": "WARNING",
            "message": Messages.PROCTORING_WARNING_SUSPICIOUS_ACTIVITY,
            "effective_violation_score": effective_violation_score,
            "risk_percentage": risk_percentage,
        }
        warning_event = ProctoringEvent(
            session_id=session.id,
            event_type=ProctoringEventType.WARNING_GENERATED.value,
            payload=warning_payload,
            occurred_at=now,
            source="SYSTEM",
        )
        self.events.add(warning_event)
        self._record_audit(
            session,
            action=ProctoringAuditAction.WARNING_GENERATED.value,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            details={
                "effective_violation_score": effective_violation_score,
                "risk_percentage": risk_percentage,
            },
        )
        logger.warning(
            "Proctoring warning generated session_id=%s score=%s",
            session.id,
            effective_violation_score,
        )
        return {
            "level": "WARNING",
            "message": Messages.PROCTORING_WARNING_SUSPICIOUS_ACTIVITY,
            "effective_violation_score": effective_violation_score,
            "risk_percentage": risk_percentage,
        }

    def ingest_event_for_attempt(
        self,
        *,
        test_id: int,
        attempt_id: int,
        workspace_id: int,
        actor_membership,
        actor_user_id: int,
        event_type: str,
        payload: dict | None = None,
        source: str = "REST",
    ) -> dict:
        # TEMP TRACE
        print(
            f"[INGEST_FOR_ATTEMPT]\nattempt_id={attempt_id}\nevent_type={event_type}\nsource={source}",
            flush=True,
        )
        logger.info(
            "[INGEST_FOR_ATTEMPT] attempt_id=%s event_type=%s source=%s",
            attempt_id,
            event_type,
            source,
        )
        attempt, _ = self._resolve_student_attempt(
            test_id, attempt_id, workspace_id, actor_membership
        )
        session = self.sessions.get_by_attempt_id(attempt.id)
        if not session:
            raise NotFoundError(Messages.PROCTORING_SESSION_NOT_FOUND_START_SESSION_FIRST)
        return self.ingest_event(
            session=session,
            event_type=event_type,
            payload=payload,
            source=source,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership.id,
        )

    def list_violations(
        self,
        *,
        test_id: int,
        attempt_id: int,
        workspace_id: int,
        actor_membership,
    ) -> list[dict]:
        attempt, test = self._resolve_attempt_view(
            test_id, attempt_id, workspace_id, actor_membership
        )
        session = self.sessions.get_by_attempt_id(attempt.id)
        if not session:
            return []
        is_student = attempt.student_membership_id == actor_membership.id
        rows = self.violations.list_for_session(session.id)
        if is_student:
            return [
                self.serialize_violation(v, student_view=True)
                for v in rows
                if v.severity in _EVIDENCE_SEVERITIES
            ]
        return [self.serialize_violation(v) for v in rows]

    def get_violation(
        self,
        *,
        test_id: int,
        attempt_id: int,
        violation_id: int,
        workspace_id: int,
        actor_membership,
    ) -> dict:
        attempt, test = self._resolve_attempt_view(
            test_id, attempt_id, workspace_id, actor_membership
        )
        session = self.sessions.get_by_attempt_id(attempt.id)
        if not session:
            raise NotFoundError(Messages.PROCTORING_SESSION_NOT_FOUND)
        violation = self.violations.get_for_session(violation_id, session.id)
        if not violation:
            raise NotFoundError(Messages.VIOLATION_NOT_FOUND)
        is_student = attempt.student_membership_id == actor_membership.id
        if is_student and violation.severity not in _EVIDENCE_SEVERITIES:
            raise ForbiddenError(Messages.INSUFFICIENT_PERMISSIONS_TO_VIEW_THIS_VIOLATION)
        return {
            "violation": self.serialize_violation(
                violation, student_view=is_student
            ),
        }

    def get_evidence_package(
        self,
        *,
        test_id: int,
        attempt_id: int,
        violation_id: int,
        workspace_id: int,
        actor_membership,
    ) -> dict:
        data = self.get_violation(
            test_id=test_id,
            attempt_id=attempt_id,
            violation_id=violation_id,
            workspace_id=workspace_id,
            actor_membership=actor_membership,
        )
        violation = self.violations.get_by_id(violation_id)
        if not violation or not violation.evidence_package:
            raise NotFoundError(Messages.EVIDENCE_PACKAGE_NOT_FOUND)
        if violation.severity not in _EVIDENCE_SEVERITIES:
            raise NotFoundError(Messages.EVIDENCE_PACKAGE_NOT_GENERATED_FOR_LOW_SEVERITY)
        return {
            "evidence": self.serialize_evidence(violation.evidence_package),
            "violation": data["violation"],
        }

    def review_violation(
        self,
        *,
        test_id: int,
        attempt_id: int,
        violation_id: int,
        workspace_id: int,
        actor_membership,
        actor_user_id: int,
        status: str,
        review_notes: str | None = None,
    ) -> dict:
        attempt, test = self._resolve_attempt_view(
            test_id, attempt_id, workspace_id, actor_membership
        )
        self._ensure_proctor_access(test, workspace_id, actor_membership)
        session = self.sessions.get_by_attempt_id(attempt.id)
        if not session:
            raise NotFoundError(Messages.PROCTORING_SESSION_NOT_FOUND)
        violation = self.violations.get_for_session(violation_id, session.id)
        if not violation:
            raise NotFoundError(Messages.VIOLATION_NOT_FOUND)

        allowed = {
            ProctoringViolationStatus.REVIEWED.value,
            ProctoringViolationStatus.DISMISSED.value,
            ProctoringViolationStatus.CONFIRMED.value,
        }
        if status not in allowed:
            raise ValidationError(Messages.STATUS_MUST_BE_ONE_OF.format(allowed=", ".join(sorted(allowed))))

        violation.status = status
        violation.reviewed_by_membership_id = actor_membership.id
        violation.reviewed_at = datetime.now(timezone.utc)
        violation.review_notes = (review_notes or "").strip() or None

        self._record_audit(
            session,
            action=ProctoringAuditAction.VIOLATION_REVIEWED.value,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership.id,
            violation_id=violation.id,
            details={"status": status, "review_notes": violation.review_notes},
        )
        db.session.commit()
        logger.info(
            "Violation id=%s reviewed status=%s by membership_id=%s",
            violation.id,
            status,
            actor_membership.id,
        )
        self._broadcast_session_monitoring_update(session)
        return {
            "message": Messages.VIOLATION_REVIEWED,
            "violation": self.serialize_violation(violation),
        }

    def list_audit_logs(
        self,
        *,
        test_id: int,
        attempt_id: int,
        workspace_id: int,
        actor_membership,
    ) -> list[dict]:
        attempt, test = self._resolve_attempt_view(
            test_id, attempt_id, workspace_id, actor_membership
        )
        self._ensure_proctor_access(test, workspace_id, actor_membership)
        session = self.sessions.get_by_attempt_id(attempt.id)
        if not session:
            return []
        rows = self.audit_logs.list_for_session(session.id)
        return [self._serialize_audit(row) for row in rows]

    def terminate_session_for_attempt(
        self,
        *,
        test_attempt_id: int,
        completed: bool = True,
        actor_user_id: int | None = None,
    ) -> ProctoringSession | None:
        session = self.sessions.get_by_attempt_id(test_attempt_id)
        if not session:
            return None
        if session.status != ProctoringSessionStatus.ACTIVE.value:
            return session

        now = datetime.now(timezone.utc)
        session.status = (
            ProctoringSessionStatus.COMPLETED.value
            if completed
            else ProctoringSessionStatus.TERMINATED.value
        )
        session.ended_at = now
        event = ProctoringEvent(
            session_id=session.id,
            event_type=ProctoringEventType.SESSION_TERMINATED.value,
            payload={"completed": completed},
            occurred_at=now,
            source="SYSTEM",
        )
        self.events.add(event)
        self._record_audit(
            session,
            action=ProctoringAuditAction.SESSION_TERMINATED.value,
            actor_user_id=actor_user_id,
            details={"completed": completed},
        )
        db.session.commit()
        logger.info(
            "Proctoring session id=%s terminated completed=%s",
            session.id,
            completed,
        )
        self._broadcast_session_monitoring_update(session)
        return session

    def _broadcast_session_monitoring_update(
        self,
        session: ProctoringSession,
        *,
        violation: ProctoringViolation | None = None,
    ) -> None:
        attempt = session.test_attempt or self.attempts.get_by_id(session.test_attempt_id)
        if not attempt:
            return
        test = attempt.test or self.tests.get_by_id(attempt.test_id)
        if not test:
            return
        self.notify_monitoring_row_updated(
            test=test,
            attempt=attempt,
            session=session,
            violation=violation,
        )

    def handle_websocket_message(
        self,
        *,
        test_id: int,
        attempt_id: int,
        workspace_id: int,
        actor_membership,
        actor_user_id: int,
        message: dict,
    ) -> dict:
        # TEMP TRACE — before any processing
        print(
            f"[WS HANDLE]\ntype={message.get('type') or message.get('event_type')}\npayload={message.get('payload') or message.get('data') or {}}",
            flush=True,
        )
        logger.info(
            "[WS HANDLE]\ntype=%s\npayload=%s",
            message.get("type") or message.get("event_type"),
            message.get("payload") or message.get("data") or {},
        )
        event_type = (message.get("type") or message.get("event_type") or "").lower()
        type_map = {
            "student_joined": ProctoringEventType.STUDENT_JOINED.value,
            "session_started": ProctoringEventType.SESSION_STARTED.value,
            "face_detected": ProctoringEventType.FACE_DETECTED.value,
            "face_lost": ProctoringEventType.FACE_LOST.value,
            "tab_switch": ProctoringEventType.TAB_SWITCH.value,
            "warning_generated": ProctoringEventType.WARNING_GENERATED.value,
            "violation_triggered": ProctoringEventType.VIOLATION_TRIGGERED.value,
            "session_terminated": ProctoringEventType.SESSION_TERMINATED.value,
            "camera_status": ProctoringEventType.CAMERA_STATUS.value,
            "microphone_activity": ProctoringEventType.MICROPHONE_ACTIVITY.value,
            "screen_inactivity": ProctoringEventType.SCREEN_INACTIVITY.value,
            "audio_anomaly": ProctoringEventType.AUDIO_ANOMALY.value,
            "multiple_faces": ProctoringEventType.MULTIPLE_FACES.value,
            "copy_paste": ProctoringEventType.COPY_PASTE.value,
            "fullscreen_exit": ProctoringEventType.FULLSCREEN_EXIT.value,
        }
        normalized = type_map.get(event_type, event_type.upper())
        payload = message.get("payload") or message.get("data") or {}

        if normalized == ProctoringEventType.STUDENT_JOINED.value:
            result = self.start_session(
                test_id=test_id,
                attempt_id=attempt_id,
                workspace_id=workspace_id,
                actor_membership=actor_membership,
                actor_user_id=actor_user_id,
                device_metadata=payload.get("device"),
                browser_metadata=payload.get("browser"),
            )
            return {"type": "session_started", "payload": result}

        result = self.ingest_event_for_attempt(
            test_id=test_id,
            attempt_id=attempt_id,
            workspace_id=workspace_id,
            actor_membership=actor_membership,
            actor_user_id=actor_user_id,
            event_type=normalized,
            payload=payload,
            source="WEBSOCKET",
        )
        response_type = "event_recorded"
        if result.get("violation"):
            response_type = "violation_triggered"
        if result.get("warning"):
            response_type = "warning_generated"
        if result.get("terminated"):
            response_type = "attempt_terminated"
        return {"type": response_type, "payload": result}

    def _create_violation(
        self,
        session: ProctoringSession,
        decision: ViolationDecision,
        *,
        trigger_event: ProctoringEvent,
        payload: dict | None,
    ) -> ProctoringViolation:
        session.violation_score = (session.violation_score or 0) + decision.score_contribution
        violation = ProctoringViolation(
            session_id=session.id,
            violation_type=decision.violation_type,
            severity=decision.severity,
            score_contribution=decision.score_contribution,
            description=decision.description,
            status=ProctoringViolationStatus.OPEN.value,
        )
        self.violations.add(violation)
        db.session.flush()
        # TEMP TRACE — remove after proctoring path diagnosis
        logger.info(
            "[CREATE_VIOLATION] violation_type=%s severity=%s score=%s session_id=%s",
            decision.violation_type,
            decision.severity,
            decision.score_contribution,
            session.id,
        )

        self._record_audit(
            session,
            action=ProctoringAuditAction.VIOLATION_CREATED.value,
            violation_id=violation.id,
            details={
                "violation_type": decision.violation_type,
                "severity": decision.severity,
            },
        )

        if decision.generate_evidence:
            self._build_evidence_package(
                session,
                violation,
                trigger_event=trigger_event,
                payload=payload,
            )

        logger.warning(
            "Violation created session_id=%s type=%s severity=%s",
            session.id,
            decision.violation_type,
            decision.severity,
        )
        return violation

    def _build_evidence_package(
        self,
        session: ProctoringSession,
        violation: ProctoringViolation,
        *,
        trigger_event: ProctoringEvent,
        payload: dict | None,
    ) -> ProctoringEvidencePackage:
        before_start, after_end = self.engine.timeline_window(
            center=trigger_event.occurred_at
        )
        before_events = self.events.list_for_session(
            session.id, since=before_start, until=trigger_event.occurred_at, limit=50
        )
        after_events = self.events.list_for_session(
            session.id, since=trigger_event.occurred_at, until=after_end, limit=50
        )

        screenshots = []
        video_ref = None
        if payload:
            for idx, shot in enumerate(payload.get("screenshots") or []):
                if isinstance(shot, str):
                    ref = self.storage.store_screenshot(
                        workspace_id=session.workspace_id,
                        session_id=session.id,
                        image_base64=shot,
                    )
                    screenshots.append({"ref": ref, "index": idx})
            clip = payload.get("video_clip_base64")
            if clip:
                video_ref = self.storage.store_video_clip(
                    workspace_id=session.workspace_id,
                    session_id=session.id,
                    video_base64=clip,
                )

        package = ProctoringEvidencePackage(
            violation_id=violation.id,
            timeline_before=[self._serialize_event(e) for e in reversed(before_events)],
            timeline_after=[self._serialize_event(e) for e in after_events],
            screenshots=screenshots or None,
            video_clip_ref=video_ref,
            device_metadata=session.device_metadata,
            browser_metadata=session.browser_metadata,
            network_metadata=(payload or {}).get("network"),
            event_logs=[self._serialize_event(trigger_event)],
        )
        self.evidence.add(package)
        self._record_audit(
            session,
            action=ProctoringAuditAction.EVIDENCE_GENERATED.value,
            violation_id=violation.id,
            details={"evidence_id": package.id},
        )
        return package

    def serialize_session(
        self, session: ProctoringSession, *, include_counts: bool = False
    ) -> dict:
        payload = {
            "id": session.id,
            "test_attempt_id": session.test_attempt_id,
            "workspace_id": session.workspace_id,
            "status": session.status,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "violation_score": session.violation_score,
            "tab_switch_count": session.tab_switch_count,
            "settings_snapshot": session.settings_snapshot,
        }
        if include_counts:
            payload["violation_count"] = len(self.violations.list_for_session(session.id))
            payload["event_count"] = len(self.events.list_for_session(session.id, limit=1000))
        return payload

    def serialize_violation(
        self, violation: ProctoringViolation, *, student_view: bool = False
    ) -> dict:
        payload = {
            "id": violation.id,
            "session_id": violation.session_id,
            "violation_type": violation.violation_type,
            "severity": violation.severity,
            "score_contribution": violation.score_contribution,
            "description": violation.description,
            "status": violation.status,
            "created_at": violation.created_at.isoformat() if violation.created_at else None,
        }
        if not student_view:
            payload["reviewed_at"] = (
                violation.reviewed_at.isoformat() if violation.reviewed_at else None
            )
            payload["review_notes"] = violation.review_notes
            payload["reviewed_by_membership_id"] = violation.reviewed_by_membership_id
        return payload

    def serialize_evidence(self, package: ProctoringEvidencePackage | None) -> dict | None:
        if not package:
            return None
        return {
            "id": package.id,
            "violation_id": package.violation_id,
            "timeline_before": package.timeline_before,
            "timeline_after": package.timeline_after,
            "screenshots": package.screenshots,
            "video_clip_ref": package.video_clip_ref,
            "device_metadata": package.device_metadata,
            "browser_metadata": package.browser_metadata,
            "network_metadata": package.network_metadata,
            "event_logs": package.event_logs,
            "created_at": package.created_at.isoformat() if package.created_at else None,
        }

    def _serialize_event(self, event: ProctoringEvent) -> dict:
        return {
            "id": event.id,
            "session_id": event.session_id,
            "event_type": event.event_type,
            "payload": event.payload,
            "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
            "source": event.source,
        }

    def _serialize_audit(self, row: ProctoringAuditLog) -> dict:
        return {
            "id": row.id,
            "session_id": row.session_id,
            "violation_id": row.violation_id,
            "action": row.action,
            "actor_membership_id": row.actor_membership_id,
            "actor_user_id": row.actor_user_id,
            "details": row.details,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def _record_audit(
        self,
        session: ProctoringSession,
        *,
        action: str,
        actor_user_id: int | None = None,
        actor_membership_id: int | None = None,
        violation_id: int | None = None,
        details: dict | None = None,
    ) -> None:
        self.audit_logs.add(
            ProctoringAuditLog(
                session_id=session.id,
                violation_id=violation_id,
                action=action,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                details=details,
            )
        )

    def _resolve_student_attempt(
        self, test_id: int, attempt_id: int, workspace_id: int, actor_membership
    ) -> tuple[TestAttempt, Test]:
        attempt = self.attempts.get_for_test(attempt_id, test_id)
        if not attempt:
            raise NotFoundError(Messages.ATTEMPT_NOT_FOUND)
        if attempt.student_membership_id != actor_membership.id:
            raise ForbiddenError(Messages.YOU_CAN_ONLY_ACCESS_YOUR_OWN_ATTEMPT)
        test = self._get_test_in_workspace(test_id, workspace_id)
        actor_link = self.subject_memberships.find_active(
            actor_membership.id, test.subject_id
        )
        if not verify_subject_student_access(actor_link):
            raise ForbiddenError(Messages.STUDENT_SUBJECT_ENROLLMENT_REQUIRED)
        return attempt, test

    def _resolve_attempt_view(
        self, test_id: int, attempt_id: int, workspace_id: int, actor_membership
    ) -> tuple[TestAttempt, Test]:
        attempt = self.attempts.get_for_test(attempt_id, test_id)
        if not attempt:
            raise NotFoundError(Messages.ATTEMPT_NOT_FOUND)
        test = self._get_test_in_workspace(test_id, workspace_id)
        if attempt.student_membership_id == actor_membership.id:
            return attempt, test
        self._ensure_proctor_access(test, workspace_id, actor_membership)
        return attempt, test

    def _ensure_proctor_access(
        self, test: Test, workspace_id: int, actor_membership
    ) -> None:
        workspace = self.workspaces.get_by_id(workspace_id)
        actor_link = self.subject_memberships.find_active(
            actor_membership.id, test.subject_id
        )
        is_creator = test.created_by_membership_id == actor_membership.id
        if not can_manage_test_attempts(
            workspace,
            actor_membership,
            actor_subject_link=actor_link,
            is_test_creator=is_creator,
        ):
            raise ForbiddenError(Messages.INSUFFICIENT_PERMISSIONS_FOR_PROCTORING_ACCESS)

    def _get_test_in_workspace(self, test_id: int, workspace_id: int) -> Test:
        test = self.tests.get_by_id_in_workspace(test_id, workspace_id)
        if not test:
            raise NotFoundError(Messages.TEST_NOT_FOUND)
        return test

    def _load_json(self, value):
        if not value:
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return None
