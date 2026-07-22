"""Unit tests for account soft-delete restore window (calendar month)."""

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from utils.account_lifecycle import (
    account_restore_deadline,
    add_one_calendar_month,
    is_within_account_restore_window,
)


TZ = ZoneInfo("Asia/Damascus")


class AccountSoftDeleteWindowTests(unittest.TestCase):
    def test_add_one_calendar_month_same_day(self):
        deleted = datetime(2026, 7, 21, 14, 30, 0, tzinfo=TZ)
        self.assertEqual(
            add_one_calendar_month(deleted),
            datetime(2026, 8, 21, 14, 30, 0, tzinfo=TZ),
        )

    def test_add_one_calendar_month_clamps_short_month(self):
        deleted = datetime(2026, 1, 31, 10, 0, 0, tzinfo=TZ)
        self.assertEqual(
            add_one_calendar_month(deleted),
            datetime(2026, 2, 28, 10, 0, 0, tzinfo=TZ),
        )

    def test_restore_window_inclusive_deadline(self):
        deleted = datetime(2026, 7, 21, 12, 0, 0, tzinfo=TZ)
        deadline = account_restore_deadline(deleted)
        self.assertTrue(is_within_account_restore_window(deleted, now=deadline))
        self.assertFalse(
            is_within_account_restore_window(
                deleted, now=datetime(2026, 8, 21, 12, 0, 1, tzinfo=TZ)
            )
        )


if __name__ == "__main__":
    unittest.main()
