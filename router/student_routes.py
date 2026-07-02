"""
Student-facing APIs — upcoming tests, dashboards, etc.
"""
from flask import Blueprint, g, jsonify

from router.decorators import handle_service_errors, require_active_student
from service.attempt_service import AttemptService

student_bp = Blueprint("student", __name__)


@student_bp.route("/tests/upcoming", methods=["GET"])
@require_active_student
@handle_service_errors
def list_upcoming_tests():
    """GET /student/tests/upcoming — published assigned tests not yet taken."""
    items = AttemptService().list_upcoming_tests(
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    )
    return jsonify(items), 200


@student_bp.route("/tests/results", methods=["GET"])
@require_active_student
@handle_service_errors
def list_graded_test_results():
    """GET /student/tests/results — fully graded attempts for the Results tab."""
    items = AttemptService().list_student_graded_results(
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        actor_user_id=g.current_user.id,
    )
    return jsonify(items), 200
