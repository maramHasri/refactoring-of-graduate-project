"""
Application timezone helpers — single local timezone for scheduling and test datetimes.

Configure via APP_TIMEZONE in .env (default Asia/Damascus).
API accepts naive local ISO strings; responses return the same format (no Z / offset).
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

_OFFSET_SUFFIX = re.compile(r"([+-]\d{2}:\d{2}(?::\d{2})?|Z)$")


def get_app_timezone_name() -> str:
    try:
        from flask import current_app

        return current_app.config.get("APP_TIMEZONE", "Asia/Damascus")
    except RuntimeError:
        return os.getenv("APP_TIMEZONE", "Asia/Damascus")


def get_app_timezone() -> ZoneInfo:
    return ZoneInfo(get_app_timezone_name())


def local_timezone_now() -> datetime:
    """Current time in the configured application timezone (aware)."""
    return datetime.now(get_app_timezone())


def ensure_local_aware(dt: datetime) -> datetime:
    """Attach or convert to application timezone."""
    tz = get_app_timezone()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def parse_local_datetime(value) -> datetime:
    """
    Parse API input as local application time.

    Accepts naive ISO strings such as ``2026-06-29T08:00:00``.
    Trailing ``Z`` or ``+00:00`` suffixes are stripped and treated as local wall time
    (for backward compatibility with older clients).
    """
    if isinstance(value, datetime):
        return ensure_local_aware(value)

    text = str(value).strip()
    if not text:
        raise ValueError("datetime value is required")

    if text.endswith("Z"):
        text = text[:-1]
    text = _OFFSET_SUFFIX.sub("", text)

    parsed = datetime.fromisoformat(text)
    return ensure_local_aware(parsed)


def format_local_datetime(dt: datetime | None) -> str | None:
    """Format for API responses — naive local ISO string, no timezone suffix."""
    if dt is None:
        return None
    local = ensure_local_aware(dt).replace(tzinfo=None)
    if local.microsecond:
        return local.isoformat(timespec="milliseconds")
    return local.strftime("%Y-%m-%dT%H:%M:%S")
