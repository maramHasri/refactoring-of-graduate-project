"""
Development-only OTP exposure for API testing (never enable in production).
"""
from flask import current_app


def should_expose_otp_in_response() -> bool:
    if not current_app.config.get("DEBUG"):
        return False
    return bool(current_app.config.get("EXPOSE_OTP_IN_DEV_RESPONSE", True))


def attach_dev_otp(payload: dict, plain_otp: str, *, email: str | None = None) -> dict:
    """
    Add dev_otp to JSON when EXPOSE_OTP_IN_DEV_RESPONSE is on (development only).
    Also logs to the server console for Swagger/Postman testing.
    """
    if not should_expose_otp_in_response():
        return payload
    payload["dev_otp"] = plain_otp
    label = email or payload.get("email") or "unknown"
    current_app.logger.warning(
        "[DEV ONLY] OTP for %s: %s — use POST /auth/verify-otp (not stored in DB as plain text)",
        label,
        plain_otp,
    )
    print(f"\n[DEV OTP] {label} -> {plain_otp}\n")
    return payload
