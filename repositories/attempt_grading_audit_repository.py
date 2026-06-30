from models import AttemptGradingAuditLog
from repositories.base_repository import BaseRepository
from utils.db import db


class AttemptGradingAuditRepository(BaseRepository):
    def add_log(
        self,
        *,
        attempt_id: int,
        action: str,
        actor_membership_id: int | None = None,
        actor_user_id: int | None = None,
        details: str | None = None,
    ) -> AttemptGradingAuditLog:
        row = AttemptGradingAuditLog(
            attempt_id=attempt_id,
            action=action,
            actor_membership_id=actor_membership_id,
            actor_user_id=actor_user_id,
            details=details,
        )
        self.add(row)
        return row

    def list_for_attempt(self, attempt_id: int) -> list[AttemptGradingAuditLog]:
        return list(
            db.session.execute(
                db.select(AttemptGradingAuditLog)
                .where(AttemptGradingAuditLog.attempt_id == attempt_id)
                .order_by(AttemptGradingAuditLog.created_at.asc(), AttemptGradingAuditLog.id.asc())
            ).scalars().all()
        )
