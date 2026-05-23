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
    VerifyEmailSchema,
)
from schemas.user_schema import LoginSchema, ResendVerificationSchema
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
    POST /auth/register — workspace owner onboarding.
    """
    data = RegisterOwnerSchema().load(request.get_json() or {})
    result = AuthService().register_workspace_owner(**data)
    response = {
        "message": "Registration successful. Check your email for the verification link.",
        **result,
    }
    if not result.get("email_sent") and result.get("dev_verification_token"):
        response["message"] += " (dev: email not sent — use dev_verification_token)"
    return response, 201


@auth_bp.route("/login", methods=["POST"])
@handle_service_errors
def login():
    """
    POST /auth/login — standard user login.
    """
    data = LoginSchema().load(request.get_json() or {})
    result = AuthService().login(**data, **_client_meta())
    return result, 200


@auth_bp.route("/superadmin/login", methods=["POST"])
@handle_service_errors
def superadmin_login():
    """
    POST /auth/superadmin/login — super admin only.
    """
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
    """
    POST /auth/logout — revoke current session.
    """
    AuthService().logout(g.access_jti)
    return {"message": "Logged out"}, 200


@auth_bp.route("/logout-all", methods=["POST"])
@require_auth
@handle_service_errors
def logout_all():
    """
    POST /auth/logout-all — revoke all sessions for user.
    """
    count = AuthService().logout_all(g.current_user.id)
    return {"message": "All sessions revoked", "count": count}, 200


@auth_bp.route("/refresh", methods=["POST"])
@handle_service_errors
def refresh():
    """
    POST /auth/refresh — issue new access token from refresh token.
    """
    data = RefreshTokenSchema().load(request.get_json() or {})
    result = AuthService().refresh_tokens(data["refresh_token"])
    return result, 200


@auth_bp.route("/verify/<token>", methods=["GET"])
@handle_service_errors
def verify_email_legacy_link(token):
    """
    Legacy/wrong link handler — email verification is POST /auth/verify-email.
    Workspace invites use GET /invites/{token}, not /auth/verify/...
    """
    return {
        "error": "Unsupported link format",
        "hint": (
            "Email verification: POST /auth/verify-email with JSON "
            '{"token": "<token from registration email>"}. '
            "Workspace invite: GET /invites/{token} then POST /invites/{token}/accept."
        ),
        "received_token_prefix": token[:20] + "..." if len(token) > 20 else token,
    }, 400


@auth_bp.route("/verify-email", methods=["POST"])
@handle_service_errors
def verify_email():
    """
    POST /auth/verify-email — mark email verified (read token, write user).
    """
    data = VerifyEmailSchema().load(request.get_json() or {})
    user = AuthService().verify_email(data["token"])
    return {
        "message": "Email verified",
        "user": {"id": user.id, "email": user.email, "email_verified": True},
    }, 200


@auth_bp.route("/resend-verification", methods=["POST"])
@handle_service_errors
def resend_verification():
    """
    POST /auth/resend-verification — create new verification token.
    """
    data = ResendVerificationSchema().load(request.get_json() or {})
    result = AuthService().resend_verification(data["email"])
    return result, 200


@auth_bp.route("/forgot-password", methods=["POST"])
@handle_service_errors
def forgot_password():
    """
    POST /auth/forgot-password — start reset flow (must NOT change password).
    """
    data = ForgotPasswordSchema().load(request.get_json() or {})
    raw = AuthService().forgot_password(data["email"])
    response = {"message": "If the account exists, reset instructions were sent"}
    if raw and request.environ.get("FLASK_ENV") == "development":
        response["dev_token"] = raw
    return response, 200


@auth_bp.route("/reset-password", methods=["POST"])
@handle_service_errors
def reset_password():
    """
    POST /auth/reset-password — complete reset + revoke sessions.
    """
    data = ResetPasswordSchema().load(request.get_json() or {})
    AuthService().reset_password(data["token"], data["new_password"])
    return {"message": "Password reset successful"}, 200


@auth_bp.route("/change-password", methods=["POST"])
@require_auth
@handle_service_errors
def change_password():
    """
    POST /auth/change-password — authenticated password change.
    """
    data = ChangePasswordSchema().load(request.get_json() or {})
    AuthService().change_password(
        g.current_user.id,
        data["current_password"],
        data["new_password"],
    )
    return {"message": "Password changed"}, 200
