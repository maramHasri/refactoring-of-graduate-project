"""
Auth API routes — thin layer over AuthService.
"""
from flask import Blueprint, g, request

from router.decorators import handle_service_errors, require_auth
from schemas.auth_schema import (
    ChangePasswordSchema,
    ForgotPasswordSchema,
    RefreshTokenSchema,
    RegisterOwnerSchema,
    ResetPasswordSchema,
    SuperAdminLoginSchema,
    VerifyOtpSchema,
)
from schemas.user_schema import LoginSchema, ResendOtpSchema
from service.auth_service import AuthService

auth_bp = Blueprint("auth", __name__)


def _client_meta():
    return {
        "ip_address": request.remote_addr,
        "user_agent": request.headers.get("User-Agent"),
    }


@auth_bp.route("/register", methods=["POST"])
@handle_service_errors
def register_owner():
    """
    POST /auth/register — submit owner registration; OTP sent by email.
    User and workspace are created after POST /auth/verify-otp.
    """
    data = RegisterOwnerSchema().load(request.get_json() or {})
    result = AuthService().register_workspace_owner(**data)
    response = {
        "message": "Registration started. Check your email for the verification code.",
        **result,
    }
    if result.get("dev_otp"):
        response["message"] += " (development: use dev_otp from response or server console)"
    return response, 201


@auth_bp.route("/login", methods=["POST"])
@handle_service_errors
def login():
    """POST /auth/login — standard user login."""
    data = LoginSchema().load(request.get_json() or {})
    result = AuthService().login(**data, **_client_meta())
    return result, 200


@auth_bp.route("/superadmin/login", methods=["POST"])
@handle_service_errors
def superadmin_login():
    """POST /auth/superadmin/login — super admin only."""
    data = SuperAdminLoginSchema().load(request.get_json() or {})
    result = AuthService().login_superadmin(
        email=data["email"],
        password=data["password"],
        **_client_meta(),
    )
    return result, 200


@auth_bp.route("/logout", methods=["POST"])
@require_auth
@handle_service_errors
def logout():
    """POST /auth/logout — revoke current session."""
    AuthService().logout(g.access_jti)
    return {"message": "Logged out"}, 200


@auth_bp.route("/logout-all", methods=["POST"])
@require_auth
@handle_service_errors
def logout_all():
    """POST /auth/logout-all — revoke all sessions for user."""
    count = AuthService().logout_all(g.current_user.id)
    return {"message": "All sessions revoked", "count": count}, 200


@auth_bp.route("/refresh", methods=["POST"])
@handle_service_errors
def refresh():
    """POST /auth/refresh — issue new access token from refresh token."""
    data = RefreshTokenSchema().load(request.get_json() or {})
    result = AuthService().refresh_tokens(data["refresh_token"])
    return result, 200


@auth_bp.route("/verify-otp", methods=["POST"])
@handle_service_errors
def verify_otp():
    """POST /auth/verify-otp — verify email OTP and complete registration if pending."""
    data = VerifyOtpSchema().load(request.get_json() or {})
    result = AuthService().verify_otp(email=data["email"], otp=data["otp"])
    return result, 200


@auth_bp.route("/resend-otp", methods=["POST"])
@handle_service_errors
def resend_otp():
    """POST /auth/resend-otp — invalidate previous OTP and send a new one."""
    data = ResendOtpSchema().load(request.get_json() or {})
    result = AuthService().resend_otp(data["email"])
    return result, 200


@auth_bp.route("/forgot-password", methods=["POST"])
@handle_service_errors
def forgot_password():
    """POST /auth/forgot-password — start reset flow (link-based, unchanged)."""
    data = ForgotPasswordSchema().load(request.get_json() or {})
    raw = AuthService().forgot_password(data["email"])
    response = {"message": "If the account exists, reset instructions were sent"}
    if raw and request.environ.get("FLASK_ENV") == "development":
        response["dev_token"] = raw
    return response, 200


@auth_bp.route("/reset-password", methods=["POST"])
@handle_service_errors
def reset_password():
    """POST /auth/reset-password — complete reset + revoke sessions."""
    data = ResetPasswordSchema().load(request.get_json() or {})
    AuthService().reset_password(data["token"], data["new_password"])
    return {"message": "Password reset successful"}, 200


@auth_bp.route("/change-password", methods=["POST"])
@require_auth
@handle_service_errors
def change_password():
    """POST /auth/change-password — authenticated password change."""
    data = ChangePasswordSchema().load(request.get_json() or {})
    AuthService().change_password(
        g.current_user.id,
        data["current_password"],
        data["new_password"],
    )
    return {"message": "Password changed"}, 200
