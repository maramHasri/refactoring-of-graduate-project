"""
Grading routes — manual grading and grading results (nested under /tests).
"""
from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_workspace_membership
from schemas.attempt_schema import ApproveFinalScoreSchema, GradeAttemptEssaysSchema
from service.attempt_service import AttemptService

grading_bp = Blueprint("grading", __name__)
_svc = lambda: AttemptService()


@grading_bp.route(
    "/<int:test_id>/attempts/<int:attempt_id>/grading/manual",
    methods=["POST"],
)
@require_workspace_membership
@handle_service_errors
def grade_pending_answers(test_id, attempt_id):
    """POST /tests/{test_id}/attempts/{attempt_id}/grading/manual — teacher manual grading."""
    data = GradeAttemptEssaysSchema().load(request.get_json() or {})
    return _svc().grade_attempt_essays(
        test_id=test_id,
        attempt_id=attempt_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        grades=data["answers"],
    ), 200


@grading_bp.route(
    "/<int:test_id>/attempts/<int:attempt_id>/grading/result",
    methods=["GET"],
)
@require_workspace_membership
@handle_service_errors
def get_grading_result(test_id, attempt_id):
    """GET /tests/{test_id}/attempts/{attempt_id}/grading/result — grading outcome."""
    return _svc().get_grading_result(
        test_id=test_id,
        attempt_id=attempt_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    ), 200


@grading_bp.route(
    "/<int:test_id>/attempts/<int:attempt_id>/grading/final-score",
    methods=["PATCH"],
)
@require_workspace_membership
@handle_service_errors
def approve_final_score(test_id, attempt_id):
    """PATCH /tests/{test_id}/attempts/{attempt_id}/grading/final-score — teacher proctoring score approval."""
    data = ApproveFinalScoreSchema().load(request.get_json() or {})
    return _svc().approve_final_score(
        test_id=test_id,
        attempt_id=attempt_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        approved=data["approved"],
        final_score=data.get("final_score"),
        reason=data.get("reason"),
    ), 200


@grading_bp.route("/<int:test_id>/attempts/<int:attempt_id>/grade", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def grade_pending_answers_legacy(test_id, attempt_id):
    """Legacy alias for POST .../grading/manual (backward compatibility)."""
    data = GradeAttemptEssaysSchema().load(request.get_json() or {})
    return _svc().grade_attempt_essays(
        test_id=test_id,
        attempt_id=attempt_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        grades=data["answers"],
    ), 200
