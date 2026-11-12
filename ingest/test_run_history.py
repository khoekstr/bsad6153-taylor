"""Run-history integration tests use connection-local temporary tables only."""
from collections import Counter
from datetime import datetime, timezone
import os
import unittest
import uuid

from ingest import test_sync as fixtures
from ingest.run_history import run_logged
from ingest.sync import ROOT, synchronize, upsert_rows


@unittest.skipUnless(os.getenv('SYNC_TEST_DATABASE') == '1', 'database tests are opt-in')
class HistoryTests(unittest.TestCase):
    def setUp(self):
        fixtures.DatabaseTests.setUp(self)
        migration = (ROOT / 'db/migrations/006_sync_runs.sql').read_text()
        ddl = migration[migration.index('CREATE TABLE sync_runs'):migration.index('CREATE INDEX')]
        self.conn.execute(ddl.replace('CREATE TABLE', 'CREATE TEMP TABLE', 1))

    def report(self):
        return self.conn.execute((ROOT / 'db/sync_status.sql').read_text()).fetchone()[0]

    def test_success_and_noop_have_separate_rows(self):
        client = fixtures.FakeClient([fixtures.page([fixtures.work()])])
        now = datetime.now(timezone.utc)
        first = run_logged(self.conn, lambda: synchronize(self.conn,client,fixtures.plan(),now=now),
                           stats=client.stats,trigger='schedule')
        self.assertEqual(first['committed_records_inserted'],1)
        second = run_logged(self.conn, lambda: synchronize(self.conn,fixtures.FakeClient([]),fixtures.plan(),now=now),stats=Counter())
        self.assertNotEqual(first['run_id'],second['run_id'])
        rows = self.conn.execute('SELECT status,records_inserted,trigger,outcome FROM sync_runs ORDER BY started_at').fetchall()
        self.assertEqual(rows,[('success',1,'schedule','completed'),('success',0,'manual','already_completed_today')])
        report=self.report()
        self.assertEqual(report['last_7_days']['works_added'],1)
        self.assertIsNotNone(report['last_successful_discovery_at'])

    def test_failed_write_rolls_back_data_but_keeps_sanitized_history(self):
        def fail():
            upsert_rows(self.conn,[fixtures.work()])
            self.conn.execute("INSERT INTO sync_state(pipeline,state) VALUES ('test','{}')")
            raise ValueError('private-password-example https://user:secret@example.com')
        with self.assertRaises(ValueError):
            run_logged(self.conn,fail,stats=Counter(records_fetched=12))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM works').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM sync_state').fetchone()[0],0)
        row=self.conn.execute('SELECT status,records_fetched,records_inserted,records_updated,error_message,finished_at FROM sync_runs').fetchone()
        self.assertEqual(row[:4],('failed',12,0,0))
        self.assertNotIn('secret@example.com',row[4])
        self.assertNotIn('private-password',row[4])
        self.assertIsNotNone(row[5])

    def test_preview_logs_zero_committed_counts_and_no_freshness(self):
        client=fixtures.FakeClient([fixtures.page([fixtures.work()])])
        result=run_logged(self.conn,lambda:synchronize(self.conn,client,fixtures.plan(),dry_run=True),stats=client.stats,dry_run=True)
        self.assertEqual(result['committed_records_inserted'],0)
        row=self.conn.execute('SELECT dry_run,records_inserted,details FROM sync_runs').fetchone()
        self.assertEqual(row[:2],(True,0))
        self.assertEqual(row[2]['proposed_records_inserted'],1)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM works').fetchone()[0],0)
        self.assertIsNone(self.report()['last_successful_discovery_at'])
        self.assertIsNone(self.report()['last_committed_work_change_at'])

    def test_empty_search_partial(self):
        client=fixtures.FakeClient([fixtures.page([]),fixtures.page([])])
        result=run_logged(self.conn,lambda:synchronize(self.conn,client,fixtures.plan()),stats=client.stats)
        self.assertEqual(result['run_status'],'partial')
        self.assertEqual(self.report()['last_7_days']['partial_runs'],1)

    def test_interrupt_records_failed(self):
        def stop():
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            run_logged(self.conn,stop,stats=Counter())
        self.assertEqual(self.conn.execute('SELECT status,outcome FROM sync_runs').fetchone(),('failed','rolled_back'))

    def test_status_constraint_rejects_unknown_value(self):
        import psycopg
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute("INSERT INTO sync_runs(run_id,status,trigger,mode) VALUES (%s,'made_up','manual','discovery_only')",(uuid.uuid4(),))

    def test_seven_day_totals_exclude_old_runs(self):
        self.conn.execute("""INSERT INTO sync_runs(run_id,started_at,finished_at,status,trigger,mode,outcome,records_inserted)
            VALUES (%s,now()-interval '9 days',now()-interval '8 days','success','manual','discovery_only','completed',5)""",(uuid.uuid4(),))
        self.assertEqual(self.report()['last_7_days']['works_added'],0)
        self.assertIsNotNone(self.report()['last_committed_work_change_at'])


if __name__ == '__main__':
    unittest.main()
