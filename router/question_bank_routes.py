"""
Question bank APIs — subject-centered content with visibility rules.
"""
from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_workspace_membership
from schemas.question_schema import CreateQuestionInBankSchema
from schemas.subject_schema import CreateQuestionBankSchema, UpdateQuestionBankSchema
from service.question_bank_service import QuestionBankService
from service.question_service import QuestionService

question_bank_bp = Blueprint("question_banks", __name__)
_svc = lambda: QuestionBankService()


@question_bank_bp.route("", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def create_question_bank():
    """
    POST /question-banks — admin or subject-assigned TEACHER.
    Requires subject_role=TEACHER on subject_memberships for non-admins.
    """
    data = CreateQuestionBankSchema().load(request.get_json() or {})
    bank = _svc().create_question_bank(
        workspace_id=g.workspace_id,
        subject_id=data["subject_id"],
        title=data["title"],
        description=data.get("description"),
        visibility=data["visibility"],
        actor_membership=g.membership,
    )
    return {
        "message": "Question bank created",
        "question_bank": _svc()._serialize_bank(bank),
    }, 201


@question_bank_bp.route("/my", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_my_question_banks():
    """GET /question-banks/my — banks created by current membership."""
    items = _svc().list_my_question_banks(g.workspace_id, g.membership)
    return {"question_banks": items, "count": len(items)}, 200


@question_bank_bp.route("/<int:bank_id>/questions", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def create_question_in_bank(bank_id):
    """
    POST /question-banks/{bankId}/questions — unified create by type_code (MCQ, TRUE_FALSE, ...).
    """
    data = CreateQuestionInBankSchema().load(request.get_json() or {})
    question = QuestionService().create_question_in_bank(
        bank_id=bank_id,
        workspace_id=g.workspace_id,
        owner_user_id=g.current_user.id,
        actor_membership=g.membership,
        payload=data,
    )
    return {
        "message": "Question created",
        "question": QuestionService().serialize_question(question),
    }, 201


@question_bank_bp.route("/<int:bank_id>/questions", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_questions_in_bank(bank_id):
    """GET /question-banks/{bankId}/questions — list questions in bank."""
    items = QuestionService().list_questions_in_bank(
        bank_id=bank_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    )
    return {"questions": items, "count": len(items)}, 200


@question_bank_bp.route("/<int:bank_id>", methods=["PATCH"])
@require_workspace_membership
@handle_service_errors
def update_question_bank(bank_id):
    """PATCH /question-banks/{id} — creator or owner/admin."""
    data = UpdateQuestionBankSchema().load(request.get_json() or {}, partial=True)
    bank = _svc().update_question_bank(
        bank_id, g.workspace_id, g.membership, data
    )
    return {
        "message": "Question bank updated",
        "question_bank": _svc()._serialize_bank(bank),
    }, 200


@question_bank_bp.route("/<int:bank_id>", methods=["DELETE"])
@require_workspace_membership
@handle_service_errors
def delete_question_bank(bank_id):
    """DELETE /question-banks/{id} — soft delete."""
    bank = _svc().archive_question_bank(bank_id, g.workspace_id, g.membership)
    return {
        "message": "Question bank archived",
        "question_bank": _svc()._serialize_bank(bank),
    }, 200
