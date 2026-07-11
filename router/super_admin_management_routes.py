from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_superadmin
from schemas.super_admin_management_schema import (
    SuperAdminUsersListQuerySchema,
    SuspendOrganizationSchema,
    SuspendUserSchema,
)
from service.super_admin_management_service import SuperAdminManagementService

super_admin_management_bp = Blueprint("super_admin_management", __name__)
_svc = lambda: SuperAdminManagementService()


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
