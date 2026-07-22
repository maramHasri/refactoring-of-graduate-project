"""
Account soft-delete lifecycle helpers.

Restore window uses one calendar month in the application timezone
(APP_TIMEZONE), not a fixed 30-day window.

Example: deleted_at local wall time 2026-07-21 14:30:00 → restore allowed
until 2026-08-21 14:30:00 (same local clock fields, clamped for short months).
"""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime

from utils.app_timezone import ensure_local_aware, local_timezone_now


def add_one_calendar_month(dt: datetime) -> datetime:
    """Return dt plus one calendar month in application timezone."""
    local = ensure_local_aware(dt)
    year = local.year
    month = local.month + 1
    if month > 12:
        month = 1
        year += 1
    day = min(local.day, monthrange(year, month)[1])
    return local.replace(year=year, month=month, day=day)


def account_restore_deadline(deleted_at: datetime) -> datetime:
    """Latest moment a soft-deleted account may be restored (inclusive)."""
    return add_one_calendar_month(deleted_at)


def is_within_account_restore_window(deleted_at: datetime, *, now: datetime | None = None) -> bool:
    current = ensure_local_aware(now) if now is not None else local_timezone_now()
    return current <= account_restore_deadline(deleted_at)
