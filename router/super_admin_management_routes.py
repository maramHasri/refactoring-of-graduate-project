from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_superadmin
from schemas.super_admin_management_schema import (
    SuperAdminUsersListQuerySchema,
    SuspendInstitutionSchema,
    SuspendUserSchema,
)
from service.super_admin_management_service import SuperAdminManagementService

super_admin_management_bp = Blueprint("super_admin_management", __name__)
_svc = lambda: SuperAdminManagementService()


@super_admin_management_bp.route(
    "/institutions/<int:institution_id>/suspend", methods=["PATCH"]
)
@require_superadmin
@handle_service_errors
def suspend_institution(institution_id):
    data = SuspendInstitutionSchema().load(request.get_json() or {})
    return _svc().suspend_institution(
        institution_id,
        reason=data["reason"],
        actor_user=g.current_user,
    ), 200


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
        institution_id=query.get("institution_id"),
        status=query.get("status"),
        search=query.get("search"),
        super_admin_only=super_admin_only,
    ), 200
