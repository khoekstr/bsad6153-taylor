from datetime import datetime, timezone
import unittest
from scripts.schedule_window import allowed


class WindowTests(unittest.TestCase):
    def test_four_dates_only(self):
        for day in range(12, 18):
            with self.subTest(day=day):
                self.assertEqual(allowed('schedule','refs/heads/main',datetime(2026,11,day,14,37,tzinfo=timezone.utc)),13 <= day <= 16)

    def test_no_annual_restart(self):
        self.assertFalse(allowed('schedule','refs/heads/main',datetime(2027,11,13,tzinfo=timezone.utc)))

    def test_manual_default_branch_only(self):
        now=datetime(2026,11,12,tzinfo=timezone.utc)
        self.assertTrue(allowed('workflow_dispatch','refs/heads/main',now))
        self.assertFalse(allowed('workflow_dispatch','refs/heads/milestone-3-sync',now))
        self.assertFalse(allowed('push','refs/heads/main',now))


if __name__ == '__main__':
    unittest.main()
