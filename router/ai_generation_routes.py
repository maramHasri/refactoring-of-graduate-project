from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_workspace_membership
from schemas.ai_generation_schema import UpdateAIGeneratedQuestionSchema
from service.test_service import TestService

ai_generation_bp = Blueprint("ai_generation", __name__)
_svc = lambda: TestService()


@ai_generation_bp.route("/ai-generation-requests/<int:request_id>", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def get_ai_generation_request(request_id):
    return _svc().get_ai_generation_request(
        request_id=request_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    ), 200


@ai_generation_bp.route("/ai-generated-questions/<int:question_id>", methods=["PUT"])
@require_workspace_membership
@handle_service_errors
def update_ai_generated_question(question_id):
    data = UpdateAIGeneratedQuestionSchema().load(request.get_json() or {})
    return {
        "message": "AI generated question updated",
        "question": _svc().update_ai_generated_question(
            generated_question_id=question_id,
            workspace_id=g.workspace_id,
            actor_membership=g.membership,
            data=data,
        ),
    }, 200


@ai_generation_bp.route("/ai-generated-questions/<int:question_id>", methods=["DELETE"])
@require_workspace_membership
@handle_service_errors
def delete_ai_generated_question(question_id):
    _svc().delete_ai_generated_question(
        generated_question_id=question_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    )
    return {"message": "AI generated question deleted"}, 200
