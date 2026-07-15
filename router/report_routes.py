from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_auth
from schemas.report_schema import CreateReportSchema
from service.report_service import ReportService

report_bp = Blueprint("reports", __name__)
_svc = lambda: ReportService()


@report_bp.route("", methods=["POST"])
@require_auth
@handle_service_errors
def create_report():
    payload = CreateReportSchema().load(request.get_json() or {})
    workspace_id = request.headers.get("X-Workspace-Id", type=int)
    return _svc().create_report(
        actor_user=g.current_user,
        title=payload["title"],
        description=payload["description"],
        category=payload["category"],
        workspace_id=workspace_id,
    ), 201


@report_bp.route("", methods=["GET"])
@require_auth
@handle_service_errors
def list_my_reports():
    return _svc().list_my_reports(actor_user=g.current_user), 200


@report_bp.route("/<int:report_id>", methods=["GET"])
@require_auth
@handle_service_errors
def get_my_report(report_id):
    return _svc().get_my_report(
        actor_user=g.current_user,
        report_id=report_id,
    ), 200
