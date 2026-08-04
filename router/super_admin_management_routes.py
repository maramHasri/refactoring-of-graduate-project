from schemas.report_schema import ReportsListQuerySchema, UpdateReportStatusSchema
from schemas.super_admin_management_schema import (
    SuperAdminUsersListQuerySchema,
    SuspendOrganizationSchema,
    SuspendUserSchema,
)
from schemas.user_schema import UpdateUserProfileSchema
from service.report_service import ReportService
from service.super_admin_management_service import SuperAdminManagementService
from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_superadmin

super_admin_management_bp = Blueprint("super_admin_management", __name__)
_svc = lambda: SuperAdminManagementService()
_report_svc = lambda: ReportService()


@super_admin_management_bp.route("/reports", methods=["GET"])
@require_superadmin
@handle_service_errors
def list_reports():
    query = ReportsListQuerySchema().load(request.args.to_dict())
    return _report_svc().list_reports_for_super_admin(
        page=query.get("page"),
        per_page=query.get("per_page"),
        status=query.get("status"),
        category=query.get("category"),
    ), 200


@super_admin_management_bp.route("/reports/<int:report_id>", methods=["GET"])
@require_superadmin
@handle_service_errors
def get_report_details(report_id):
    return _report_svc().get_report_for_super_admin(report_id), 200


@super_admin_management_bp.route("/reports/<int:report_id>", methods=["PATCH"])
@require_superadmin
@handle_service_errors
def update_report_status(report_id):
    payload = UpdateReportStatusSchema().load(request.get_json() or {})
    return _report_svc().update_report_status(
        report_id,
        status=payload["status"],
    ), 200


@super_admin_management_bp.route(
    "/organizations/<int:organization_id>/suspend", methods=["PATCH"]
)
@require_superadmin
@handle_service_errors
def suspend_organization(organization_id):
    data = SuspendOrganizationSchema().load(request.get_json() or {})
    return _svc().suspend_organization(
        organization_id,
        reason=data["reason"],
        actor_user=g.current_user,
    ), 200


@super_admin_management_bp.route(
    "/organizations/<int:organization_id>/restore", methods=["POST"]
)
@require_superadmin
@handle_service_errors
def restore_organization(organization_id):
    return _svc().restore_organization(
        organization_id,
        actor_user=g.current_user,
    ), 200


@super_admin_management_bp.route(
    "/organizations/<int:organization_id>", methods=["GET"]
)
@require_superadmin
@handle_service_errors
def get_organization_details(organization_id):
    return _svc().get_organization_details(organization_id), 200


@super_admin_management_bp.route("/users/<int:user_id>/suspend", methods=["PATCH"])
@require_superadmin
@handle_service_errors
def suspend_user(user_id):
    data = SuspendUserSchema().load(request.get_json() or {})
    return _svc().suspend_user(
        user_id,
        reason=data["reason"],
        actor_user=g.current_user,
    ), 200


@super_admin_management_bp.route("/users/<int:user_id>/restore", methods=["POST"])
@require_superadmin
@handle_service_errors
def restore_user(user_id):
    return _svc().restore_user(
        user_id,
        actor_user=g.current_user,
    ), 200


@super_admin_management_bp.route("/users/<int:user_id>", methods=["GET"])
@require_superadmin
@handle_service_errors
def get_user_details(user_id):
    return _svc().get_user_details(user_id), 200


@super_admin_management_bp.route("/users/<int:user_id>", methods=["PATCH"])
@require_superadmin
@handle_service_errors
def update_user(user_id):
    """PATCH /api/super-admin/users/{user_id} — update full_name and/or phone_number."""
    data = UpdateUserProfileSchema(only=("full_name", "phone_number")).load(
        request.get_json() or {},
        partial=True,
    )
    return _svc().update_user(user_id, data, actor_user=g.current_user), 200


@super_admin_management_bp.route("/users/<int:user_id>", methods=["DELETE"])
@require_superadmin
@handle_service_errors
def hard_delete_user(user_id):
    """DELETE /api/super-admin/users/{user_id} — permanent delete (not soft-delete)."""
    return _svc().hard_delete_user(user_id, actor_user=g.current_user), 200


@super_admin_management_bp.route("/users", methods=["GET"])
@require_superadmin
@handle_service_errors
def list_users():
    query = SuperAdminUsersListQuerySchema().load(request.args.to_dict())
    role = query.get("role")
    super_admin_only = role == "SUPER_ADMIN"
    if super_admin_only:
        role = None
    return _svc().list_users(
        page=query.get("page"),
        per_page=query.get("per_page"),
        role=role,
        organization_id=query.get("organization_id"),
        status=query.get("status"),
        search=query.get("search"),
        super_admin_only=super_admin_only,
    ), 200
