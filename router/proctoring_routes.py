"""Proctoring REST routes — nested under exam attempts."""
from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_workspace_membership
from schemas.proctoring_schema import (
    IngestProctoringEventSchema,
    ReviewViolationSchema,
    StartProctoringSessionSchema,
)
from service.proctoring_service import ProctoringService

proctoring_bp = Blueprint("proctoring", __name__)
_svc = lambda: ProctoringService()


@proctoring_bp.route("/<int:test_id>/proctoring/sessions", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_test_proctoring_sessions(test_id):
    """GET /tests/{test_id}/proctoring/sessions — active monitoring sessions (proctor)."""
    items = _svc().list_test_sessions(
        test_id=test_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    )
    return {"sessions": items, "count": len(items)}, 200


@proctoring_bp.route(
    "/<int:test_id>/attempts/<int:attempt_id>/proctoring/session", methods=["POST"]
)
@require_workspace_membership
@handle_service_errors
def start_proctoring_session(test_id, attempt_id):
    """POST /tests/{test_id}/attempts/{attempt_id}/proctoring/session"""
    data = StartProctoringSessionSchema().load(request.get_json() or {})
    return _svc().start_session(
        test_id=test_id,
        attempt_id=attempt_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        actor_user_id=g.current_user.id,
        device_metadata=data.get("device_metadata"),
        browser_metadata=data.get("browser_metadata"),
    ), 201


@proctoring_bp.route(
    "/<int:test_id>/attempts/<int:attempt_id>/proctoring/session", methods=["GET"]
)
@require_workspace_membership
@handle_service_errors
def get_proctoring_session(test_id, attempt_id):
    """GET /tests/{test_id}/attempts/{attempt_id}/proctoring/session"""
    return _svc().get_session_status(
        test_id=test_id,
        attempt_id=attempt_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    ), 200


@proctoring_bp.route(
    "/<int:test_id>/attempts/<int:attempt_id>/proctoring/events", methods=["POST"]
)
@require_workspace_membership
@handle_service_errors
def ingest_proctoring_event(test_id, attempt_id):
    """POST /tests/{test_id}/attempts/{attempt_id}/proctoring/events — REST event ingest."""
    data = IngestProctoringEventSchema().load(request.get_json() or {})
    result = _svc().ingest_event_for_attempt(
        test_id=test_id,
        attempt_id=attempt_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        actor_user_id=g.current_user.id,
        event_type=data["event_type"],
        payload=data.get("payload"),
        source="REST",
    )
    return {"message": "Event recorded", **result}, 201


@proctoring_bp.route(
    "/<int:test_id>/attempts/<int:attempt_id>/proctoring/violations", methods=["GET"]
)
@require_workspace_membership
@handle_service_errors
def list_violations(test_id, attempt_id):
    """GET /tests/{test_id}/attempts/{attempt_id}/proctoring/violations"""
    items = _svc().list_violations(
        test_id=test_id,
        attempt_id=attempt_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    )
    return {"violations": items, "count": len(items)}, 200


@proctoring_bp.route(
    "/<int:test_id>/attempts/<int:attempt_id>/proctoring/violations/<int:violation_id>",
    methods=["GET"],
)
@require_workspace_membership
@handle_service_errors
def get_violation(test_id, attempt_id, violation_id):
    """GET .../proctoring/violations/{violation_id}"""
    return _svc().get_violation(
        test_id=test_id,
        attempt_id=attempt_id,
        violation_id=violation_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    ), 200


@proctoring_bp.route(
    "/<int:test_id>/attempts/<int:attempt_id>/proctoring/violations/<int:violation_id>/evidence",
    methods=["GET"],
)
@require_workspace_membership
@handle_service_errors
def get_evidence(test_id, attempt_id, violation_id):
    """GET .../proctoring/violations/{violation_id}/evidence"""
    return _svc().get_evidence_package(
        test_id=test_id,
        attempt_id=attempt_id,
        violation_id=violation_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    ), 200


@proctoring_bp.route(
    "/<int:test_id>/attempts/<int:attempt_id>/proctoring/violations/<int:violation_id>/review",
    methods=["POST"],
)
@require_workspace_membership
@handle_service_errors
def review_violation(test_id, attempt_id, violation_id):
    """POST .../proctoring/violations/{violation_id}/review — proctor/admin."""
    data = ReviewViolationSchema().load(request.get_json() or {})
    return _svc().review_violation(
        test_id=test_id,
        attempt_id=attempt_id,
        violation_id=violation_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        actor_user_id=g.current_user.id,
        status=data["status"],
        review_notes=data.get("review_notes"),
    ), 200


@proctoring_bp.route(
    "/<int:test_id>/attempts/<int:attempt_id>/proctoring/audit-logs", methods=["GET"]
)
@require_workspace_membership
@handle_service_errors
def list_audit_logs(test_id, attempt_id):
    """GET .../proctoring/audit-logs — proctor/admin audit trail."""
    items = _svc().list_audit_logs(
        test_id=test_id,
        attempt_id=attempt_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    )
    return {"audit_logs": items, "count": len(items)}, 200
