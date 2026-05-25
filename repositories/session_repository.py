from datetime import datetime, timezone

from models import UserSession
from repositories.base_repository import BaseRepository
from utils.db import db


class SessionRepository(BaseRepository):
    def get_by_id(self, session_id: int) -> UserSession | None:
        return db.session.get(UserSession, session_id)

    def find_active_by_jti(self, jti: str) -> UserSession | None:
        return db.session.execute(
            db.select(UserSession).where(
                UserSession.access_token_id == jti,
                UserSession.is_active.is_(True),
            )
        ).scalar_one_or_none()

    def deactivate(self, session: UserSession) -> None:
        session.is_active = False

    def deactivate_all_for_user(self, user_id: int) -> int:
        sessions = (
            db.session.execute(
                db.select(UserSession).where(
                    UserSession.user_id == user_id,
                    UserSession.is_active.is_(True),
                )
            )
            .scalars()
            .all()
        )
        for session in sessions:
            session.is_active = False
        return len(sessions)

    def touch(self, session: UserSession) -> None:
        session.last_used_at = datetime.now(timezone.utc)
