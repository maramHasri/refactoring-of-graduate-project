"""
RBAC guards and JWT authentication.

Workspace context is NOT embedded in JWT — frontend sends X-Workspace-Id when needed.
"""
from functools import wraps

from flask import current_app, g, jsonify, request
from marshmallow import ValidationError as MarshmallowValidationError

from service.exceptions import ServiceError, UnauthorizedError
from service.session_service import SessionService
from utils.jwt_tokens import decode_token
from repositories.user_repository import UserRepository


def _extract_bearer_token() -> str | None:
    auth = (request.headers.get("Authorization") or "").strip()
    if not auth:
        return None
    if auth.startswith("Bearer "):
        return auth[7:].strip() or None
    # Swagger often sends the raw JWT without a "Bearer " prefix
    return auth


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_bearer_token()
        if not token:
            return jsonify({"error": "Missing authorization token"}), 401

        payload = decode_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401
        if payload.get("type") != "access":
            return jsonify(
                {
                    "error": "Invalid access token",
                    "hint": "Use access_token from login, not refresh_token",
                }
            ), 401

        jti = payload.get("jti")
        user_id = int(payload["sub"])
        try:
            SessionService().validate_access_jti(jti)
            from utils.db import db

            db.session.commit()
        except UnauthorizedError as exc:
            return jsonify({"error": exc.message}), 401

        user = UserRepository().get_by_id(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 401

        g.current_user = user
        g.access_jti = jti
        g.token_payload = payload
        return f(*args, **kwargs)

    return decorated


def require_superadmin(f):
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        if not g.current_user.is_superadmin:
            return jsonify({"error": "Super admin access required"}), 403
        return f(*args, **kwargs)

    return decorated


def require_workspace_membership(f):
    """Requires X-Workspace-Id header and active membership (super admin bypass)."""

    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        if g.current_user.is_superadmin:
            g.workspace_id = request.headers.get("X-Workspace-Id", type=int)
            g.membership = None
            return f(*args, **kwargs)

        workspace_id = request.headers.get("X-Workspace-Id", type=int)
        if not workspace_id:
            return jsonify({"error": "X-Workspace-Id header is required"}), 400

        from repositories.workspace_repository import MembershipRepository

        membership = MembershipRepository().find_by_user_and_workspace(
            g.current_user.id, workspace_id
        )
        if not membership or membership.status != "ACTIVE":
            return jsonify({"error": "Not an active member of this workspace"}), 403

        g.workspace_id = workspace_id
        g.membership = membership
        return f(*args, **kwargs)

    return decorated


def handle_service_errors(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except MarshmallowValidationError as exc:
            return jsonify({"errors": exc.messages}), 400
        except ServiceError as exc:
            return jsonify({"error": exc.message}), exc.status_code
        except Exception:
            current_app.logger.exception("Unhandled error in %s", f.__name__)
            payload = {"error": "Internal server error"}
            if current_app.config.get("DEBUG"):
                payload["detail"] = "See server logs for traceback"
            return jsonify(payload), 500

    return decorated
