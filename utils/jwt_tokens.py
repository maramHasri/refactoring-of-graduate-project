"""
JWT strategy:
- Access tokens carry user identity + jti (maps to user_sessions.access_token_id).
- Refresh tokens carry user id + session id; they do NOT replace workspace context.
- Workspace selection is a frontend concern; JWT is global per user.
"""
import uuid
from datetime import datetime, timezone

import jwt
from flask import current_app


def _utcnow():
    return datetime.now(timezone.utc)


def create_access_token(
    user_id: int,
    *,
    is_superadmin: bool = False,
    jti: str | None = None,
) -> tuple[str, str]:
    jti = jti or str(uuid.uuid4())
    expires = _utcnow() + current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "type": "access",
        "is_superadmin": is_superadmin,
        "exp": expires,
        "iat": _utcnow(),
    }
    token = jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")
    return token, jti


def create_refresh_token(user_id: int, session_id: int) -> str:
    expires = _utcnow() + current_app.config["JWT_REFRESH_TOKEN_EXPIRES"]
    payload = {
        "sub": str(user_id),
        "sid": session_id,
        "type": "refresh",
        "exp": expires,
        "iat": _utcnow(),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"],
        )
    except jwt.PyJWTError:
        return None
