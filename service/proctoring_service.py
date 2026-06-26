"""
Proctoring orchestration — sessions, events, violations, evidence, audit.
"""
from __future__ import annotations

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
from repositories.test_repository import TestRepository
from repositories.workspace_repository import WorkspaceRepository
from service.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from service.proctoring_storage import ProctoringStorageService
from service.proctoring_violation_engine import ProctoringViolationEngine, ViolationDecision
from utils.academic_rbac import can_manage_test_attempts, verify_subject_student_access
from utils.db import db
from utils.enums import (
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


class ProctoringService:
    def __init__(self):
        self.sessions = ProctoringSessionRepository()
        self.events = ProctoringEventRepository()
        self.violations = ProctoringViolationRepository()
        self.evidence = ProctoringEvidenceRepository()
        self.audit_logs = ProctoringAuditLogRepository()
        self.attempts = TestAttemptRepository()
        self.tests = TestRepository()
        self.subject_memberships = SubjectMembershipRepository()
        self.workspaces = WorkspaceRepository()
        self.engine = ProctoringViolationEngine()
        self.storage = ProctoringStorageService()

    def is_proctoring_enabled(self, test: Test) -> bool:
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
            raise ValidationError("Proctoring session requires an in-progress attempt")

        session = self.ensure_session_for_attempt(
            test_attempt=attempt,
            workspace_id=workspace_id,
            test=test,
            device_metadata=device_metadata,
            browser_metadata=browser_metadata,
        )
        if not session:
            raise ValidationError("Proctoring is not enabled for this test")
        return {
            "message": "Proctoring session active",
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
            raise NotFoundError("Proctoring session not found")
        return {"session": self.serialize_session(session, include_counts=True)}

    def list_test_sessions(
        self, *, test_id: int, workspace_id: int, actor_membership
    ) -> list[dict]:
        test = self._get_test_in_workspace(test_id, workspace_id)
        self._ensure_proctor_access(test, workspace_id, actor_membership)
        rows = self.sessions.list_active_for_test(test.id, workspace_id)
        return [self.serialize_session(row, include_counts=True) for row in rows]

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
            raise ConflictError("Proctoring session is not active")

        occurred_at = occurred_at or datetime.now(timezone.utc)
        normalized = (event_type or "").upper()

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

        result = {"event": self._serialize_event(event), "violation": None, "warning": None}

        if not skip_violation_check:
            decision = self.engine.evaluate(
                session, normalized, payload=payload, occurred_at=occurred_at
            )
            if decision:
                violation = self._create_violation(
                    session,
                    decision,
                    trigger_event=event,
                    payload=payload,
                )
                result["violation"] = self.serialize_violation(violation)
                if decision.severity in _EVIDENCE_SEVERITIES:
                    result["evidence"] = self.serialize_evidence(
                        violation.evidence_package
                    )

        db.session.commit()
        return result

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
        attempt, _ = self._resolve_student_attempt(
            test_id, attempt_id, workspace_id, actor_membership
        )
        session = self.sessions.get_by_attempt_id(attempt.id)
        if not session:
            raise NotFoundError("Proctoring session not found — start session first")
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
            raise NotFoundError("Proctoring session not found")
        violation = self.violations.get_for_session(violation_id, session.id)
        if not violation:
            raise NotFoundError("Violation not found")
        is_student = attempt.student_membership_id == actor_membership.id
        if is_student and violation.severity not in _EVIDENCE_SEVERITIES:
            raise ForbiddenError("Insufficient permissions to view this violation")
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
            raise NotFoundError("Evidence package not found")
        if violation.severity not in _EVIDENCE_SEVERITIES:
            raise NotFoundError("Evidence package not generated for LOW severity")
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
            raise NotFoundError("Proctoring session not found")
        violation = self.violations.get_for_session(violation_id, session.id)
        if not violation:
            raise NotFoundError("Violation not found")

        allowed = {
            ProctoringViolationStatus.REVIEWED.value,
            ProctoringViolationStatus.DISMISSED.value,
            ProctoringViolationStatus.CONFIRMED.value,
        }
        if status not in allowed:
            raise ValidationError(f"status must be one of: {', '.join(sorted(allowed))}")

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
        return {
            "message": "Violation reviewed",
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
        return session

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
            raise NotFoundError("Attempt not found")
        if attempt.student_membership_id != actor_membership.id:
            raise ForbiddenError("You can only access your own attempt")
        test = self._get_test_in_workspace(test_id, workspace_id)
        actor_link = self.subject_memberships.find_active(
            actor_membership.id, test.subject_id
        )
        if not verify_subject_student_access(actor_link):
            raise ForbiddenError("Student subject enrollment required")
        return attempt, test

    def _resolve_attempt_view(
        self, test_id: int, attempt_id: int, workspace_id: int, actor_membership
    ) -> tuple[TestAttempt, Test]:
        attempt = self.attempts.get_for_test(attempt_id, test_id)
        if not attempt:
            raise NotFoundError("Attempt not found")
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
            raise ForbiddenError("Insufficient permissions for proctoring access")

    def _get_test_in_workspace(self, test_id: int, workspace_id: int) -> Test:
        test = self.tests.get_by_id_in_workspace(test_id, workspace_id)
        if not test:
            raise NotFoundError("Test not found")
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
