"""
Student-facing APIs — upcoming tests, dashboards, etc.
"""
from flask import Blueprint, g, jsonify, request

from router.decorators import handle_service_errors, require_active_student
from schemas.attempt_schema import StudentExamsListQuerySchema, StudentRecentExamsQuerySchema
from service.attempt_service import AttemptService
from service.student_analytics_service import StudentAnalyticsService

student_bp = Blueprint("student", __name__)


@student_bp.route("/tests", methods=["GET"])
@require_active_student
@handle_service_errors
def list_student_exams():
    """GET /student/tests — all assigned exams across lifecycle states."""
    query = StudentExamsListQuerySchema().load(request.args.to_dict())
    return AttemptService().list_student_exams(
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        actor_user_id=g.current_user.id,
        page=query.get("page"),
        per_page=query.get("per_page"),
        lifecycle_status=query.get("lifecycle_status"),
    ), 200


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


@student_bp.route("/tests/<int:test_id>/entry", methods=["GET"])
@require_active_student
@handle_service_errors
def get_exam_entry(test_id):
    """GET /student/tests/{test_id}/entry — read-only Exam Entry Screen payload."""
    return AttemptService().get_exam_entry(
        test_id=test_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    ), 200


@student_bp.route("/recent-exams", methods=["GET"])
@require_active_student
@handle_service_errors
def list_recent_exams():
    """GET /student/recent-exams — recent attempts for the Student Dashboard table."""
    query = StudentRecentExamsQuerySchema().load(request.args.to_dict())
    return AttemptService().list_recent_exams(
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        actor_user_id=g.current_user.id,
        page=query.get("page"),
        per_page=query.get("per_page"),
    ), 200


@student_bp.route("/dashboard", methods=["GET"])
@require_active_student
@handle_service_errors
def get_student_dashboard():
    """GET /student/dashboard — performance overview for the Student Dashboard."""
    return StudentAnalyticsService().get_dashboard_analytics(
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        actor_user_id=g.current_user.id,
    ), 200


@student_bp.route("/performance-summary", methods=["GET"])
@require_active_student
@handle_service_errors
def get_student_performance_summary():
    """GET /student/performance-summary — compact graded-performance summary."""
    return StudentAnalyticsService().get_performance_summary(
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        actor_user_id=g.current_user.id,
    ), 200


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
