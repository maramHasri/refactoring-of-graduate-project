"""
Proctoring WebSocket channels.

Student ingest (unchanged):
  ws://host/ws/proctoring/tests/{test_id}/attempts/{attempt_id}?token=<JWT>&workspace_id=<id>

Teacher live monitor (delta only; REST snapshot remains source of truth):
  ws://host/ws/proctoring/tests/{test_id}/monitor?token=<JWT>&workspace_id=<id>

Client message format (student):
  { "type": "tab_switch", "payload": { ... } }

Server message types (student):
  session_started | event_recorded | violation_triggered | warning_generated |
  attempt_terminated | error

Server message types (teacher monitor):
  subscribed | student_row_updated | violation_created | error
"""

from __future__ import annotations

from utils.messages import Messages

import json
import logging
import threading
from collections import defaultdict

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

# In-memory teacher monitor subscribers: test_id -> set[ws]
_teacher_monitor_lock = threading.Lock()
_teacher_monitor_subscribers: dict[int, set] = defaultdict(set)


def subscribe_teacher_monitor(test_id: int, ws) -> None:
    with _teacher_monitor_lock:
        _teacher_monitor_subscribers[int(test_id)].add(ws)


def unsubscribe_teacher_monitor(test_id: int, ws) -> None:
    with _teacher_monitor_lock:
        bucket = _teacher_monitor_subscribers.get(int(test_id))
        if not bucket:
            return
        bucket.discard(ws)
        if not bucket:
            _teacher_monitor_subscribers.pop(int(test_id), None)


def broadcast_teacher_monitor(test_id: int, message: dict) -> None:
    """Fan-out compact deltas to teachers watching this test (same process only)."""
    payload = json.dumps(message)
    with _teacher_monitor_lock:
        subscribers = list(_teacher_monitor_subscribers.get(int(test_id), set()))
    dead = []
    for ws in subscribers:
        try:
            ws.send(payload)
        except Exception:
            dead.append(ws)
            logger.exception(
                "Teacher monitor broadcast failed test_id=%s", test_id
            )
    for ws in dead:
        unsubscribe_teacher_monitor(test_id, ws)


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

    @sock.route("/ws/proctoring/tests/<int:test_id>/monitor")
    def teacher_monitor_ws(ws, test_id: int):
        """
        Teacher/admin live monitoring room for one test.

        Authz uses the same proctor access helper as REST monitoring.
        On reconnect, clients must re-fetch GET /tests/{test_id}/monitoring.
        """
        try:
            user, membership, workspace_id = _authenticate_ws()
        except ServiceError as exc:
            ws.send(json.dumps({"type": "error", "payload": {"error": exc.message}}))
            return

        if membership is None:
            ws.send(
                json.dumps(
                    {
                        "type": "error",
                        "payload": {
                            "error": Messages.INSUFFICIENT_PERMISSIONS_FOR_PROCTORING_ACCESS
                        },
                    }
                )
            )
            return

        svc = ProctoringService()
        try:
            test = svc._get_test_in_workspace(test_id, workspace_id)
            svc._ensure_proctor_access(test, workspace_id, membership)
        except ServiceError as exc:
            ws.send(json.dumps({"type": "error", "payload": {"error": exc.message}}))
            return
        except Exception:
            logger.exception("Teacher monitor authz failed test_id=%s", test_id)
            ws.send(
                json.dumps(
                    {
                        "type": "error",
                        "payload": {"error": Messages.INTERNAL_SERVER_ERROR},
                    }
                )
            )
            return

        subscribe_teacher_monitor(test_id, ws)
        logger.info(
            "Teacher monitor connected user_id=%s test_id=%s", user.id, test_id
        )
        ws.send(
            json.dumps(
                {
                    "type": "subscribed",
                    "payload": {
                        "test_id": test_id,
                        "message": (
                            "Subscribed to live monitoring deltas. "
                            "Re-fetch REST snapshot after reconnect."
                        ),
                    },
                }
            )
        )

        try:
            while True:
                raw = ws.receive()
                if raw is None:
                    break
                # Teacher monitor is push-only; ignore client payloads except ping.
                try:
                    message = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    continue
                if (message.get("type") or "").lower() == "ping":
                    ws.send(json.dumps({"type": "pong", "payload": {}}))
        finally:
            unsubscribe_teacher_monitor(test_id, ws)
            logger.info(
                "Teacher monitor disconnected user_id=%s test_id=%s",
                user.id,
                test_id,
            )
