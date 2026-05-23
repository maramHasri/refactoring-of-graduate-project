"""
Session management: ties JWT access jti to user_sessions rows.
"""
from datetime import datetime, timedelta, timezone

from flask import current_app

from models import UserSession
from repositories.session_repository import SessionRepository
from service.exceptions import UnauthorizedError
from utils.jwt_tokens import create_access_token, create_refresh_token


class SessionService:
    def __init__(self):
        self.repo = SessionRepository()

    def create_user_session(
        self,
        user_id: int,
        *,
        is_superadmin: bool = False,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str, UserSession]:
        access_expires = datetime.now(timezone.utc) + current_app.config[
            "JWT_ACCESS_TOKEN_EXPIRES"
        ]
        session = UserSession(
            user_id=user_id,
            access_token_id="pending",
            ip_address=ip_address,
            user_agent=user_agent,
            is_active=True,
            expires_at=access_expires,
            last_used_at=datetime.now(timezone.utc),
        )
        self.repo.add(session)
        self.repo.flush()

        access_token, jti = create_access_token(
            user_id, is_superadmin=is_superadmin, jti=None
        )
        session.access_token_id = jti
        refresh_token = create_refresh_token(user_id, session.id)
        return access_token, refresh_token, session

    def validate_access_jti(self, jti: str) -> UserSession:
        session = self.repo.find_active_by_jti(jti)
        if not session:
            raise UnauthorizedError("Session is invalid or expired")
        if session.expires_at < datetime.now(timezone.utc):
            self.repo.deactivate(session)
            self.repo.commit()
            raise UnauthorizedError("Session has expired")
        self.repo.touch(session)
        return session

    def refresh_session(self, refresh_token: str) -> tuple[str, str, UserSession]:
        from utils.jwt_tokens import decode_token

        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid refresh token")

        session = self.repo.get_by_id(int(payload["sid"]))
        if not session or not session.is_active:
            raise UnauthorizedError("Session is no longer active")

        user_id = int(payload["sub"])
        if session.user_id != user_id:
            raise UnauthorizedError("Refresh token mismatch")

        from repositories.user_repository import UserRepository

        user = UserRepository().get_by_id(user_id)
        is_superadmin = bool(user and user.is_superadmin)

        access_token, jti = create_access_token(
            user_id, is_superadmin=is_superadmin
        )
        session.access_token_id = jti
        session.expires_at = datetime.now(timezone.utc) + current_app.config[
            "JWT_ACCESS_TOKEN_EXPIRES"
        ]
        session.last_used_at = datetime.now(timezone.utc)
        new_refresh = create_refresh_token(user_id, session.id)
        return access_token, new_refresh, session
