"""
Proctoring WebSocket channel — real-time event streaming.

Connect: ws://host/ws/proctoring/tests/{test_id}/attempts/{attempt_id}?token=<JWT>&workspace_id=<id>

Client message format:
  { "type": "tab_switch", "payload": { ... } }

Server message types:
  session_started | event_recorded | violation_triggered | error
"""

from __future__ import annotations

from utils.messages import Messages

import json
import logging

from flask import request
from flask_sock import Sock

from repositories.user_repository import UserRepository
from repositories.workspace_repository import MembershipRepository
from service.exceptions import ServiceError
from service.proctoring_service import ProctoringService
from service.session_service import SessionService
from utils.db import db
from utils.jwt_tokens import decode_token

logger = logging.getLogger(__name__)
sock = Sock()


def _authenticate_ws() -> tuple:
    token = request.args.get("token") or request.headers.get("Authorization", "")
    if token.startswith("Bearer "):
        token = token[7:].strip()
    if not token:
        raise ServiceError(Messages.MISSING_TOKEN, 401)

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise ServiceError(Messages.INVALID_ACCESS_TOKEN, 401)

    SessionService().validate_access_jti(payload.get("jti"))
    db.session.commit()

    user = UserRepository().get_by_id(int(payload["sub"]))
    if not user:
        raise ServiceError(Messages.USER_NOT_FOUND, 401)

    workspace_id = request.args.get("workspace_id", type=int)
    if not workspace_id:
        raise ServiceError(Messages.WORKSPACE_ID_QUERY_PARAMETER_IS_REQUIRED, 400)

    membership = MembershipRepository().find_by_user_and_workspace(
        user.id, workspace_id
    )
    if not membership or membership.status != "ACTIVE":
        if not user.is_superadmin:
            raise ServiceError(Messages.NOT_AN_ACTIVE_MEMBER_OF_THIS_WORKSPACE, 403)

    return user, membership, workspace_id


def register_proctoring_websocket(app) -> None:
    sock.init_app(app)

    @sock.route("/ws/proctoring/tests/<int:test_id>/attempts/<int:attempt_id>")
    def proctoring_ws(ws, test_id: int, attempt_id: int):
        try:
            user, membership, workspace_id = _authenticate_ws()
        except ServiceError as exc:
            ws.send(json.dumps({"type": "error", "payload": {"error": exc.message}}))
            return

        logger.info(
            "WebSocket connected user_id=%s test_id=%s attempt_id=%s",
            user.id,
            test_id,
            attempt_id,
        )
        svc = ProctoringService()

        while True:
            raw = ws.receive()
            if raw is None:
                break
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                ws.send(
                    json.dumps(
                        {
                            "type": "error",
                            "payload": {"error": Messages.INVALID_JSON_MESSAGE},
                        }
                    )
                )
                continue

            try:
                response = svc.handle_websocket_message(
                    test_id=test_id,
                    attempt_id=attempt_id,
                    workspace_id=workspace_id,
                    actor_membership=membership,
                    actor_user_id=user.id,
                    message=message,
                )
                ws.send(json.dumps(response))
            except ServiceError as exc:
                ws.send(
                    json.dumps({"type": "error", "payload": {"error": exc.message}})
                )
            except Exception:
                logger.exception("WebSocket proctoring handler error")
                ws.send(
                    json.dumps(
                        {
                            "type": "error",
                            "payload": {"error": Messages.INTERNAL_SERVER_ERROR},
                        }
                    )
                )

        logger.info(
            "WebSocket disconnected user_id=%s attempt_id=%s", user.id, attempt_id
        )
