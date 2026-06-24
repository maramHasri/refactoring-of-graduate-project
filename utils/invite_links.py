"""
Frontend invite URLs — user-facing links open the React app, not the API server.
"""
from flask import current_app


def frontend_base_url() -> str:
    return current_app.config.get(
        "FRONTEND_BASE_URL", "http://localhost:5173"
    ).rstrip("/")


def invite_preview_url(raw_token: str) -> str:
    return f"{frontend_base_url()}/invites/{raw_token}"


def invite_register_url(raw_token: str) -> str:
    return f"{frontend_base_url()}/invites/{raw_token}/register"


def invite_accept_url(raw_token: str) -> str:
    return f"{frontend_base_url()}/invites/{raw_token}/accept"


def invite_link_bundle(raw_token: str) -> dict[str, str]:
    return {
        "preview_url": invite_preview_url(raw_token),
        "register_url": invite_register_url(raw_token),
        "accept_url": invite_accept_url(raw_token),
    }
