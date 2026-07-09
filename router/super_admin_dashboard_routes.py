from flask import Blueprint

from router.decorators import handle_service_errors, require_superadmin
from service.super_admin_dashboard_service import SuperAdminDashboardService

super_admin_dashboard_bp = Blueprint("super_admin_dashboard", __name__)


@super_admin_dashboard_bp.route("/dashboard", methods=["GET"])
@require_superadmin
@handle_service_errors
def get_super_admin_dashboard():
    return SuperAdminDashboardService().get_dashboard(), 200
