"""
Development-only invite token exposure for API testing (never enable in production).
"""
from flask import current_app


def should_expose_invite_in_response() -> bool:
    if not current_app.config.get("DEBUG"):
        return False
    return bool(current_app.config.get("EXPOSE_INVITE_IN_DEV_RESPONSE", True))


def log_dev_invite_token(*, email: str, raw_token: str, workspace_id: int) -> None:
    if not should_expose_invite_in_response():
        return
    current_app.logger.warning(
        "[DEV ONLY] Invite token for %s (workspace %s): %s",
        email,
        workspace_id,
        raw_token,
    )
    print(
        f"\n[DEV INVITE] {email} (workspace {workspace_id}) -> {raw_token}\n"
        f"  preview:  POST /invites/{raw_token}/accept (existing user)\n"
        f"  register: POST /invites/{raw_token}/register (new user)\n"
    )


def attach_dev_invite(response: dict, *, raw_token: str) -> dict:
    if not should_expose_invite_in_response():
        return response
    response["dev_token"] = raw_token
    return response
