"""
Student-facing APIs — upcoming tests, dashboards, etc.
"""
from flask import Blueprint, g, jsonify

from router.decorators import handle_service_errors, require_active_student
from service.attempt_service import AttemptService
from service.student_analytics_service import StudentAnalyticsService

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


@student_bp.route("/subjects/<int:subject_id>/analytics", methods=["GET"])
@require_active_student
@handle_service_errors
def get_subject_analytics(subject_id):
    """GET /student/subjects/{subject_id}/analytics — topic performance for graded attempts."""
    data = StudentAnalyticsService().get_subject_analytics(
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        actor_user_id=g.current_user.id,
        subject_id=subject_id,
    )
    return jsonify(data), 200


@student_bp.route("/courses/<int:course_id>/analytics", methods=["GET"])
@require_active_student
@handle_service_errors
def get_course_analytics_legacy(course_id):
    """Legacy alias. course == subject in this system."""
    data = StudentAnalyticsService().get_course_analytics(
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        actor_user_id=g.current_user.id,
        course_id=course_id,
    )
    return jsonify(data), 200


@student_bp.route("/tests/<int:test_id>/analytics", methods=["GET"])
@require_active_student
@handle_service_errors
def get_test_analytics(test_id):
    """GET /student/tests/{test_id}/analytics — topic mastery for one graded attempt."""
    data = StudentAnalyticsService().get_test_analytics(
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        actor_user_id=g.current_user.id,
        test_id=test_id,
    )
    return jsonify(data), 200
