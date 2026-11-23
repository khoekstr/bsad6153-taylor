from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from scripts.schedule_window import allowed, main


class WindowTests(unittest.TestCase):
    def test_scheduled_and_manual_runs_are_eligible_on_main(self):
        for event in ('schedule', 'workflow_dispatch'):
            with self.subTest(event=event):
                self.assertTrue(allowed(event, 'refs/heads/main'))

    def test_other_branches_and_events_cannot_sync(self):
        for event in ('schedule', 'workflow_dispatch', 'push', 'pull_request', None):
            for ref in ('refs/heads/main', 'refs/heads/milestone-4', None):
                with self.subTest(event=event, ref=ref):
                    expected = ref == 'refs/heads/main' and event in ('schedule', 'workflow_dispatch')
                    self.assertEqual(allowed(event, ref), expected)

    def test_workflow_has_one_ongoing_monday_thursday_schedule(self):
        workflow_path = Path(__file__).resolve().parents[1] / '.github/workflows/sync.yml'
        workflow = workflow_path.read_text(encoding='utf-8')
        schedules = re.findall(r"^\s+- cron: '([^']+)'", workflow, flags=re.MULTILINE)
        self.assertEqual(len(schedules), 1)
        minute, hour, day, month, weekday = schedules[0].split()
        self.assertEqual((day, month, weekday), ('*', '*', '1,4'))
        self.assertIn('timezone: America/Chicago', workflow)
        self.assertTrue(0 <= int(minute) <= 59)
        self.assertTrue(0 <= int(hour) <= 23)

    def test_main_writes_github_output(self):
        for event, expected in (('schedule', 'true'), ('workflow_dispatch', 'true'), ('push', 'false')):
            with self.subTest(event=event), tempfile.TemporaryDirectory() as folder:
                output_path = Path(folder) / 'github-output'
                environment = {
                    'GITHUB_EVENT_NAME': event,
                    'GITHUB_REF': 'refs/heads/main',
                    'GITHUB_OUTPUT': str(output_path),
                }
                with patch.dict(os.environ, environment), redirect_stdout(io.StringIO()):
                    main()
                self.assertEqual(output_path.read_text(encoding='utf-8'), f'run_sync={expected}\n')


if __name__ == '__main__':
    unittest.main()
