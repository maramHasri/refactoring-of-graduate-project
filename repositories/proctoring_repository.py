from datetime import datetime, timedelta, timezone

from models import (
    ProctoringAuditLog,
    ProctoringEvent,
    ProctoringEvidencePackage,
    ProctoringSession,
    ProctoringViolation,
)
from repositories.base_repository import BaseRepository
from utils.db import db
from utils.enums import ProctoringSessionStatus, ProctoringViolationStatus


class ProctoringSessionRepository(BaseRepository):
    def get_by_id(self, session_id: int) -> ProctoringSession | None:
        return db.session.get(ProctoringSession, session_id)

    def get_by_attempt_id(self, test_attempt_id: int) -> ProctoringSession | None:
        return db.session.execute(
            db.select(ProctoringSession).where(
                ProctoringSession.test_attempt_id == test_attempt_id
            )
        ).scalar_one_or_none()

    def list_active_for_test(self, test_id: int, workspace_id: int) -> list[ProctoringSession]:
        from models import TestAttempt

        return list(
            db.session.execute(
                db.select(ProctoringSession)
                .join(TestAttempt, TestAttempt.id == ProctoringSession.test_attempt_id)
                .where(
                    TestAttempt.test_id == test_id,
                    ProctoringSession.workspace_id == workspace_id,
                    ProctoringSession.status == ProctoringSessionStatus.ACTIVE.value,
                )
                .order_by(ProctoringSession.started_at.desc())
            ).scalars().all()
        )

    def map_by_attempt_ids(
        self, attempt_ids: list[int]
    ) -> dict[int, ProctoringSession]:
        if not attempt_ids:
            return {}
        rows = db.session.execute(
            db.select(ProctoringSession).where(
                ProctoringSession.test_attempt_id.in_(attempt_ids)
            )
        ).scalars().all()
        return {int(row.test_attempt_id): row for row in rows}


class ProctoringEventRepository(BaseRepository):
    def list_for_session(
        self,
        session_id: int,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 500,
        ascending: bool = False,
    ) -> list[ProctoringEvent]:
        query = db.select(ProctoringEvent).where(ProctoringEvent.session_id == session_id)
        if since:
            query = query.where(ProctoringEvent.occurred_at >= since)
        if until:
            query = query.where(ProctoringEvent.occurred_at <= until)
        order = (
            ProctoringEvent.occurred_at.asc()
            if ascending
            else ProctoringEvent.occurred_at.desc()
        )
        query = query.order_by(order).limit(limit)
        return list(db.session.execute(query).scalars().all())

    def count_for_sessions(self, session_ids: list[int]) -> dict[int, int]:
        if not session_ids:
            return {}
        rows = db.session.execute(
            db.select(
                ProctoringEvent.session_id,
                db.func.count(ProctoringEvent.id),
            )
            .where(ProctoringEvent.session_id.in_(session_ids))
            .group_by(ProctoringEvent.session_id)
        ).all()
        return {int(session_id): int(count) for session_id, count in rows}

    def count_by_type_since(
        self, session_id: int, event_type: str, since: datetime
    ) -> int:
        return (
            db.session.execute(
                db.select(db.func.count(ProctoringEvent.id)).where(
                    ProctoringEvent.session_id == session_id,
                    ProctoringEvent.event_type == event_type,
                    ProctoringEvent.occurred_at >= since,
                )
            ).scalar()
            or 0
        )

    def face_lost_duration_seconds(
        self, session_id: int, *, now: datetime | None = None
    ) -> float:
        """Seconds since the most recent FACE_LOST/NO_FACE without a FACE_DETECTED after it."""
        now = now or datetime.now(timezone.utc)
        events = self.list_for_session(session_id, limit=100)
        if not events:
            return 0.0
        events = sorted(events, key=lambda e: e.occurred_at, reverse=True)
        lost_at = None
        for event in events:
            if event.event_type in ("FACE_LOST", "NO_FACE"):
                lost_at = event.occurred_at
                break
            if event.event_type == "FACE_DETECTED":
                return 0.0
        if not lost_at:
            return 0.0
        return max(0.0, (now - lost_at).total_seconds())


class ProctoringViolationRepository(BaseRepository):
    def get_by_id(self, violation_id: int) -> ProctoringViolation | None:
        return db.session.get(ProctoringViolation, violation_id)

    def get_for_session(self, violation_id: int, session_id: int) -> ProctoringViolation | None:
        return db.session.execute(
            db.select(ProctoringViolation).where(
                ProctoringViolation.id == violation_id,
                ProctoringViolation.session_id == session_id,
            )
        ).scalar_one_or_none()

    def list_for_session(self, session_id: int) -> list[ProctoringViolation]:
        return list(
            db.session.execute(
                db.select(ProctoringViolation)
                .where(ProctoringViolation.session_id == session_id)
                .order_by(ProctoringViolation.created_at.desc())
            ).scalars().all()
        )

    def map_for_sessions(
        self, session_ids: list[int]
    ) -> dict[int, list[ProctoringViolation]]:
        if not session_ids:
            return {}
        rows = db.session.execute(
            db.select(ProctoringViolation)
            .where(ProctoringViolation.session_id.in_(session_ids))
            .order_by(ProctoringViolation.created_at.desc())
        ).scalars().all()
        result: dict[int, list[ProctoringViolation]] = {
            session_id: [] for session_id in session_ids
        }
        for row in rows:
            result.setdefault(int(row.session_id), []).append(row)
        return result

    def count_for_sessions(self, session_ids: list[int]) -> dict[int, int]:
        if not session_ids:
            return {}
        rows = db.session.execute(
            db.select(
                ProctoringViolation.session_id,
                db.func.count(ProctoringViolation.id),
            )
            .where(ProctoringViolation.session_id.in_(session_ids))
            .group_by(ProctoringViolation.session_id)
        ).all()
        return {int(session_id): int(count) for session_id, count in rows}


class ProctoringEvidenceRepository(BaseRepository):
    def get_by_violation_id(self, violation_id: int) -> ProctoringEvidencePackage | None:
        return db.session.execute(
            db.select(ProctoringEvidencePackage).where(
                ProctoringEvidencePackage.violation_id == violation_id
            )
        ).scalar_one_or_none()


class ProctoringAuditLogRepository(BaseRepository):
    def list_for_session(self, session_id: int, *, limit: int = 200) -> list[ProctoringAuditLog]:
        return list(
            db.session.execute(
                db.select(ProctoringAuditLog)
                .where(ProctoringAuditLog.session_id == session_id)
                .order_by(ProctoringAuditLog.created_at.desc())
                .limit(limit)
            ).scalars().all()
        )
