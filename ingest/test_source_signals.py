"""Opt-in database checks using temporary tables only, after migration 008."""
import os
import unittest
from copy import deepcopy
from pathlib import Path
from ingest.test_sync import work
from ingest.sync import upsert_rows

@unittest.skipUnless(os.getenv('SYNC_TEST_DATABASE') == '1', 'requires temporary-table database checks')
class SourceSignalTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        from dotenv import dotenv_values
        self.conn = psycopg.connect(dotenv_values(Path(__file__).resolve().parents[1]/'.env')['DATABASE_URL'])
        self.addCleanup(self.conn.close)
        self.conn.execute('CREATE TEMP TABLE works (LIKE public.works INCLUDING ALL)')
        self.conn.execute('CREATE TEMP TABLE authorships (LIKE public.authorships INCLUDING ALL)')
        self.conn.execute('CREATE TEMP TABLE work_assessments (LIKE public.work_assessments INCLUDING ALL)')

    def test_saved_source_signals_and_replay(self):
        record = work()
        record.update(cited_by_count=0, is_retracted=False,
                      primary_location={'source': {'display_name': 'Example Journal'}})
        upsert_rows(self.conn, [record])
        first = self.conn.execute('SELECT cited_by_count,publication_name,is_retracted,metadata_checked_at FROM works').fetchone()
        self.assertEqual(first[:3], (0, 'Example Journal', False))
        self.assertIsNotNone(first[3])
        self.assertEqual(upsert_rows(self.conn, [record], allow_updates=True)['records_updated'], 0)
        self.assertEqual(self.conn.execute('SELECT metadata_checked_at FROM works').fetchone()[0], first[3])
        changed = deepcopy(record); changed.update(cited_by_count=12, is_retracted=True)
        self.assertEqual(upsert_rows(self.conn, [changed], allow_updates=True)['records_updated'], 1)
        self.assertEqual(self.conn.execute('SELECT cited_by_count,is_retracted FROM works').fetchone(), (12, True))

    def test_missing_and_invalid_values_are_unknown(self):
        record = work(); record.update(cited_by_count=-1, is_retracted='unknown')
        upsert_rows(self.conn, [record])
        self.assertEqual(self.conn.execute('SELECT cited_by_count,publication_name,is_retracted FROM works').fetchone(), (None,None,None))

    def test_simplified_and_legacy_imports_remain_idempotent(self):
        import hashlib
        from ingest.load import load_assessments
        upsert_rows(self.conn, [work()])
        assessment = dict(categories=['Learning'], value_rating=4, value_reason='Relevant',
                          summary='Finding.', relevance_reason='Fits interests', review_basis='abstract',
                          assessment_context='Test', assessment_reason='Initial', model_used='test')
        digest = hashlib.sha256(b'Evidence').hexdigest()
        row = ('test:new', 'https://openalex.org/W1', digest, assessment)
        self.assertEqual(load_assessments(self.conn, [row]), 1)
        self.assertEqual(load_assessments(self.conn, [row]), 0)
        legacy = dict(assessment, evidence_assessment='Small sample.', novelty_reason='Unknown history.')
        self.assertEqual(load_assessments(self.conn, [('test:legacy', row[1], digest, legacy)]), 1)
        summary, context = self.conn.execute("SELECT summary,assessment_context FROM work_assessments WHERE import_key='test:legacy'").fetchone()
        self.assertIn('Small sample.', summary)
        self.assertIn('Unknown history.', context)
