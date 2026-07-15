"""User profile routes — authenticated self-service only."""

from utils.messages import Messages
from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_auth
from schemas.user_schema import UpdateUserProfileSchema
from service.user_service import UserService

user_bp = Blueprint("users", __name__)
_svc = lambda: UserService()


@user_bp.route("/me", methods=["GET"])
@require_auth
@handle_service_errors
def get_my_profile():
    """GET /users/me — current user profile from JWT."""
    return _svc().get_profile(g.current_user), 200


@user_bp.route("/me", methods=["PATCH"])
@require_auth
@handle_service_errors
def update_my_profile():
    """PATCH /users/me — update full_name, phone_number, or avatar_url."""
    data = UpdateUserProfileSchema().load(request.get_json() or {}, partial=True)
    user = _svc().update_profile(g.current_user, data)
    return {
        "message": Messages.PROFILE_UPDATED_SUCCESSFULLY,
        "user": _svc().serialize_profile(user),
    }, 200
