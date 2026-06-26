"""
Exam attempt runtime routes — nested under /tests/{test_id}/attempts.
"""
from flask import Blueprint, g

from router.decorators import handle_service_errors, require_workspace_membership
from schemas.attempt_schema import (
    BulkSaveAttemptAnswersSchema,
    UpdateAttemptAnswerSchema,
)
from service.attempt_service import AttemptService

attempt_bp = Blueprint("attempts", __name__)
_svc = lambda: AttemptService()


@attempt_bp.route("/available", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_available_tests():
    """GET /tests/available — published tests the current user may take."""
    items = _svc().list_available_tests(
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    )
    return {"tests": items, "count": len(items)}, 200


@attempt_bp.route("/<int:test_id>/attempts", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def start_attempt(test_id):
    """POST /tests/{test_id}/attempts — start or resume an in-progress attempt."""
    result = _svc().start_or_resume_attempt(
        test_id=test_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        actor_user_id=g.current_user.id,
    )
    status = 200 if result.get("resumed") else 201
    return result, status


@attempt_bp.route("/<int:test_id>/attempts/current", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def get_current_attempt(test_id):
    """GET /tests/{test_id}/attempts/current — resume in-progress attempt."""
    return _svc().get_current_attempt(
        test_id=test_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    ), 200


@attempt_bp.route("/<int:test_id>/attempts", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_attempts(test_id):
    """GET /tests/{test_id}/attempts — teacher/admin list of attempts."""
    items = _svc().list_test_attempts(
        test_id=test_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    )
    return {"attempts": items, "count": len(items)}, 200


@attempt_bp.route("/<int:test_id>/attempts/<int:attempt_id>", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def get_attempt(test_id, attempt_id):
    """GET /tests/{test_id}/attempts/{attempt_id} — attempt detail."""
    return _svc().get_attempt(
        test_id=test_id,
        attempt_id=attempt_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        student_view=True,
    ), 200


@attempt_bp.route("/<int:test_id>/attempts/<int:attempt_id>/answers", methods=["PUT"])
@require_workspace_membership
@handle_service_errors
def autosave_answers(test_id, attempt_id):
    """PUT /tests/{test_id}/attempts/{attempt_id}/answers — bulk autosave."""
    from flask import request

    data = BulkSaveAttemptAnswersSchema().load(request.get_json() or {})
    return _svc().save_answers(
        test_id=test_id,
        attempt_id=attempt_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        answers=data["answers"],
    ), 200


@attempt_bp.route(
    "/<int:test_id>/attempts/<int:attempt_id>/answers/<int:test_question_id>",
    methods=["PATCH"],
)
@require_workspace_membership
@handle_service_errors
def update_answer(test_id, attempt_id, test_question_id):
    """PATCH /tests/{test_id}/attempts/{attempt_id}/answers/{test_question_id}"""
    from flask import request

    data = UpdateAttemptAnswerSchema().load(request.get_json() or {}, partial=True)
    return _svc().update_answer(
        test_id=test_id,
        attempt_id=attempt_id,
        test_question_id=test_question_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        data=data,
    ), 200


@attempt_bp.route("/<int:test_id>/attempts/<int:attempt_id>/submit", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def submit_attempt(test_id, attempt_id):
    """POST /tests/{test_id}/attempts/{attempt_id}/submit — student submit."""
    return _svc().submit_attempt(
        test_id=test_id,
        attempt_id=attempt_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    ), 200


@attempt_bp.route(
    "/<int:test_id>/attempts/<int:attempt_id>/force-submit", methods=["POST"]
)
@require_workspace_membership
@handle_service_errors
def force_submit_attempt(test_id, attempt_id):
    """POST /tests/{test_id}/attempts/{attempt_id}/force-submit — teacher/admin."""
    return _svc().force_submit_attempt(
        test_id=test_id,
        attempt_id=attempt_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    ), 200


@attempt_bp.route("/<int:test_id>/attempts/<int:attempt_id>/timeout", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def timeout_attempt(test_id, attempt_id):
    """POST /tests/{test_id}/attempts/{attempt_id}/timeout — finalize on timer expiry."""
    return _svc().timeout_attempt(
        test_id=test_id,
        attempt_id=attempt_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    ), 200
