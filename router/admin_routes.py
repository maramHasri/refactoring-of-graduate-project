"""
Super admin APIs — institution approval workflow (by owner user_id).
"""
from flask import Blueprint, request

from router.decorators import handle_service_errors, require_superadmin
from schemas.admin_schema import RejectInstitutionSchema
from service.institution_admin_service import InstitutionAdminService

admin_bp = Blueprint("admin", __name__)
_svc = lambda: InstitutionAdminService()


@admin_bp.route("/institutions/pending", methods=["GET"])
@require_superadmin
@handle_service_errors
def list_pending_institutions():
    """GET /admin/institutions/pending — users awaiting institution approval."""
    items = _svc().list_pending_institutions()
    return {"institutions": items, "count": len(items)}, 200


@admin_bp.route("/institutions/<int:user_id>", methods=["GET"])
@require_superadmin
@handle_service_errors
def get_institution(user_id):
    """GET /admin/institutions/{user_id} — full registration details."""
    item = _svc().get_institution_request(user_id)
    return {"institution": item}, 200


@admin_bp.route("/institutions/<int:user_id>/approve", methods=["POST"])
@require_superadmin
@handle_service_errors
def approve_institution(user_id):
    """POST /admin/institutions/{user_id}/approve — creates institution workspace."""
    result = _svc().approve_institution(user_id)
    return result, 200


@admin_bp.route("/institutions/<int:user_id>/reject", methods=["POST"])
@require_superadmin
@handle_service_errors
def reject_institution(user_id):
    """POST /admin/institutions/{user_id}/reject"""
    data = RejectInstitutionSchema().load(request.get_json() or {})
    result = _svc().reject_institution(user_id, reason=data["reason"])
    return result, 200
