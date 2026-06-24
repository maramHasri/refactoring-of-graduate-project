"""
Development-only invite token exposure for API testing (never enable in production).
"""
from flask import current_app

from utils.invite_links import invite_link_bundle


def should_expose_invite_in_response() -> bool:
    if not current_app.config.get("DEBUG"):
        return False
    return bool(current_app.config.get("EXPOSE_INVITE_IN_DEV_RESPONSE", True))


def log_dev_invite_token(*, email: str, raw_token: str, workspace_id: int) -> None:
    if not should_expose_invite_in_response():
        return
    links = invite_link_bundle(raw_token)
    current_app.logger.warning(
        "[DEV ONLY] Invite token for %s (workspace %s): %s",
        email,
        workspace_id,
        raw_token,
    )
    print(
        f"\n[DEV INVITE] {email} (workspace {workspace_id}) -> {raw_token}\n"
        f"  preview:  {links['preview_url']}\n"
        f"  register: {links['register_url']}\n"
        f"  accept:   {links['accept_url']}\n"
        f"  API register: POST /invites/{raw_token}/register\n"
        f"  API accept:   POST /invites/{raw_token}/accept\n"
    )


def attach_dev_invite(response: dict, *, raw_token: str) -> dict:
    if not should_expose_invite_in_response():
        return response
    response["dev_token"] = raw_token
    return response
