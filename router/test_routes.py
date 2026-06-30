from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_workspace_membership
from schemas.test_schema import (
    AIGenerateQuestionsSchema,
    AddBankQuestionsToTestSchema,
    AddManualQuestionsToTestSchema,
    AddQuestionsFromBankSelectionSchema,
    AssignStudentsToTestSchema,
    CreateTestSchema,
    ExamBlueprintSchema,
    ScheduleTestSchema,
    UpdateTestSchema,
    UpdateTestQuestionSchema,
)
from service.test_service import TestService

test_bp = Blueprint("tests", __name__)
_svc = lambda: TestService()


@test_bp.route("", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def create_test():
    data = CreateTestSchema().load(request.get_json() or {})
    test = _svc().create_test(
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        data=data,
    )
    return {
        "message": "Test created successfully",
        "test": _svc().serialize_test_created(test),
    }, 201


@test_bp.route("/my", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_my_tests():
    items = _svc().list_my_tests(g.membership)
    return {"tests": items, "count": len(items)}, 200


@test_bp.route("/<int:test_id>", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def get_test(test_id):
    payload = _svc().get_test(
        test_id=test_id, workspace_id=g.workspace_id, actor_membership=g.membership
    )
    return payload, 200


@test_bp.route("/<int:test_id>", methods=["PATCH"])
@require_workspace_membership
@handle_service_errors
def update_test(test_id):
    data = UpdateTestSchema().load(request.get_json() or {}, partial=True)
    test = _svc().update_test(
        test_id=test_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        data=data,
    )
    return {"message": "Test updated", "test": _svc().serialize_test_updated(test)}, 200


@test_bp.route("/<int:test_id>", methods=["DELETE"])
@require_workspace_membership
@handle_service_errors
def delete_test(test_id):
    _svc().delete_test(
        test_id=test_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    )
    return {"message": "Test deleted successfully"}, 200


@test_bp.route("/<int:test_id>/questions", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def add_questions_to_test(test_id):
    data = AddBankQuestionsToTestSchema().load(request.get_json() or {})
    items = _svc().add_questions_from_bank(
        test_id=test_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        question_ids=data["question_ids"],
        source_type=data["source_type"],
    )
    return {"message": "Questions added to test", "questions": items, "count": len(items)}, 201


@test_bp.route("/<int:test_id>/questions/manual", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def add_manual_questions_to_test(test_id):
    data = AddManualQuestionsToTestSchema().load(request.get_json() or {})
    items = _svc().add_manual_questions(
        test_id=test_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        questions=data["questions"],
    )
    return {"message": "Manual questions added", "questions": items, "count": len(items)}, 201


@test_bp.route("/<int:test_id>/questions/import-csv", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def import_csv_questions_to_test(test_id):
    result = _svc().import_questions_from_csv(
        test_id=test_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        file_storage=request.files.get("csv_file"),
    )
    return result, 201


@test_bp.route("/<int:test_id>/questions/from-bank", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def add_bank_selected_questions_to_test(test_id):
    data = AddQuestionsFromBankSelectionSchema().load(request.get_json() or {})
    items = _svc().add_questions_from_bank_selection(
        test_id=test_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        bank_id=data["bank_id"],
        question_ids=data["question_ids"],
    )
    return {"message": "Question bank selection added", "questions": items, "count": len(items)}, 201


@test_bp.route("/<int:test_id>/questions/random-from-banks", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def add_random_questions_to_test(test_id):
    data = ExamBlueprintSchema().load(request.get_json() or {})
    return _svc().generate_exam_from_blueprint(
        test_id=test_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        banks_blueprint=data["banks"],
    ), 201


@test_bp.route("/<int:test_id>/questions/ai-generate", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def add_ai_questions_to_test(test_id):
    data = AIGenerateQuestionsSchema().load(request.get_json() or {})
    items, ai_model, subject_name = _svc().add_ai_generated_questions(
        test_id=test_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        count=data["count"],
        type_code=data["type_code"],
        difficulty=data.get("difficulty"),
        topics=data.get("topics"),
        learning_objectives=data.get("learning_objectives"),
        additional_instructions=data.get("additional_instructions"),
    )
    return {
        "message": "AI questions added",
        "questions": items,
        "count": len(items),
        "ai_model": ai_model,
        "subject_name": subject_name,
    }, 201


@test_bp.route("/<int:test_id>/assign-students", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def assign_students_to_test(test_id):
    data = AssignStudentsToTestSchema().load(request.get_json() or {})
    count = _svc().assign_students_to_test(
        test_id=test_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        student_membership_ids=data["student_membership_ids"],
    )
    return {"message": "Students assigned successfully", "count": count}, 201


@test_bp.route("/<int:test_id>/assigned-students", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_assigned_students(test_id):
    items = _svc().list_assigned_students(
        test_id=test_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    )
    return {"students": items, "count": len(items)}, 200


@test_bp.route("/<int:test_id>/assigned-students/<int:membership_id>", methods=["DELETE"])
@require_workspace_membership
@handle_service_errors
def remove_assigned_student(test_id, membership_id):
    _svc().remove_assigned_student(
        test_id=test_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        student_membership_id=membership_id,
    )
    return {"message": "Student removed from assigned list"}, 200


@test_bp.route("/<int:test_id>/questions/<int:test_question_id>", methods=["PATCH"])
@require_workspace_membership
@handle_service_errors
def update_test_question(test_id, test_question_id):
    data = UpdateTestQuestionSchema().load(request.get_json() or {}, partial=True)
    item = _svc().update_test_question(
        test_id=test_id,
        test_question_id=test_question_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        data=data,
    )
    return {"message": "Test question updated", "question": item}, 200


@test_bp.route("/<int:test_id>/questions/<int:test_question_id>", methods=["DELETE"])
@require_workspace_membership
@handle_service_errors
def delete_test_question(test_id, test_question_id):
    _svc().delete_test_question(
        test_id=test_id,
        test_question_id=test_question_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    )
    return {"message": "Test question removed"}, 200


@test_bp.route("/<int:test_id>/publish-now", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def publish_test_now(test_id):
    test = _svc().publish_now(
        test_id=test_id, workspace_id=g.workspace_id, actor_membership=g.membership
    )
    return {"message": "Test published", "test": _svc().serialize_test(test)}, 200


@test_bp.route("/<int:test_id>/schedule-publication", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def schedule_test_publication(test_id):
    data = ScheduleTestSchema().load(request.get_json() or {})
    test = _svc().schedule_publication(
        test_id=test_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        publish_at=data["publish_at"],
    )
    return {"message": "Test scheduled", "test": _svc().serialize_test(test)}, 200


@test_bp.route("/<int:test_id>/close", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def close_test(test_id):
    test = _svc().close_test(
        test_id=test_id, workspace_id=g.workspace_id, actor_membership=g.membership
    )
    return {"message": "Test closed", "test": _svc().serialize_test(test)}, 200


@test_bp.route("/<int:test_id>/archive", methods=["POST"])
@require_workspace_membership
@handle_service_errors
def archive_test(test_id):
    test = _svc().archive_test(
        test_id=test_id, workspace_id=g.workspace_id, actor_membership=g.membership
    )
    return {"message": "Test archived", "test": _svc().serialize_test(test)}, 200
