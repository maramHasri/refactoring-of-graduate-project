"""Proctoring Integrity Report APIs — independent from Support /reports."""

from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_workspace_membership
from schemas.proctoring_integrity_report_schema import (
    IntegrityReportsListQuerySchema,
    ReviewIntegrityReportSchema,
)
from service.proctoring_integrity_report_service import ProctoringIntegrityReportService

integrity_report_bp = Blueprint("proctoring_integrity_reports", __name__)
_svc = lambda: ProctoringIntegrityReportService()


@integrity_report_bp.route("/integrity-reports", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def list_integrity_reports():
    """GET /proctoring/integrity-reports — owner or test-creator scoped list."""
    query = IntegrityReportsListQuerySchema().load(request.args.to_dict())
    return _svc().list_reports(
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        page=query.get("page"),
        per_page=query.get("per_page"),
        status=query.get("status"),
        test_id=query.get("test_id"),
        subject_id=query.get("subject_id"),
        student_membership_id=query.get("student_membership_id"),
        search=query.get("search"),
        date_from=query.get("date_from"),
        date_to=query.get("date_to"),
    ), 200


@integrity_report_bp.route("/integrity-reports/<int:report_id>", methods=["GET"])
@require_workspace_membership
@handle_service_errors
def get_integrity_report(report_id):
    """GET /proctoring/integrity-reports/{id}"""
    return _svc().get_report(
        report_id=report_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
    ), 200


@integrity_report_bp.route("/integrity-reports/<int:report_id>", methods=["PATCH"])
@require_workspace_membership
@handle_service_errors
def review_integrity_report(report_id):
    """PATCH /proctoring/integrity-reports/{id} — CONFIRMED or DISMISSED."""
    payload = ReviewIntegrityReportSchema().load(request.get_json() or {})
    return _svc().review_report(
        report_id=report_id,
        workspace_id=g.workspace_id,
        actor_membership=g.membership,
        status=payload["status"],
        review_note=payload.get("review_note"),
    ), 200
