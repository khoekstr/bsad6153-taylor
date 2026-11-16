"""CSV contract checks and opt-in read-only database safety checks."""
import csv
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from evals.check_reference import FIELDS, ROOT, check, read_questions, compare_reports


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.rows = read_questions(ROOT/'evals/golden_questions.csv')

    def test_agreed_set_and_sources(self):
        self.assertEqual(len(self.rows), 15)
        self.assertEqual(sum(r['source'] == 'baseline' for r in self.rows), 8)
        self.assertEqual(sum(r['category'] == 'should_decline' for r in self.rows), 3)

    def rejected(self, rows):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'questions.csv'
            with path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaises(ValueError):
                read_questions(path)

    def test_duplicate_id_rejected(self):
        self.rows[1]['id'] = 'Q01'
        self.rejected(self.rows)

    def test_decline_sql_rejected(self):
        self.rows[-1]['reference_sql'] = 'SELECT 1'
        self.rejected(self.rows)

    def test_missing_baseline_source_rejected(self):
        self.rows[0]['source'] = 'other'
        self.rejected(self.rows)

    def test_admin_connection_rejected_before_question_execution(self):
        conn = Mock()
        conn.execute.return_value.fetchone.return_value = ('postgres','postgres','on',None)
        with self.assertRaises(ValueError):
            check(conn, self.rows)
        self.assertFalse(any(call.kwargs.get('prepare') for call in conn.execute.call_args_list))

    def test_comparison_detects_values_not_just_row_counts(self):
        from copy import deepcopy
        before = {'passed': True, 'as_of': 'earlier', 'questions_sha256': 'same',
                  'results': [{'id':'Q01', 'status':'pass', 'sql_sha256':'same',
                               'columns':['count'], 'rows': [[5]]}]}
        after = deepcopy(before)
        after['as_of'] = 'later'
        after['results'][0]['rows'] = [(5,)]
        self.assertEqual(compare_reports(before, after)['unchanged'], ['Q01'])
        after['results'][0]['rows'] = [(6,)]
        self.assertEqual(compare_reports(before, after)['changed'], ['Q01'])
        after['questions_sha256'] = 'different'
        with self.assertRaises(ValueError):
            compare_reports(before, after)


@unittest.skipUnless(os.getenv('REFERENCE_TEST_DATABASE') == '1', 'opt-in reader database checks')
class ReaderSafetyTests(unittest.TestCase):
    def connect(self):
        import psycopg
        from dotenv import dotenv_values
        return psycopg.connect(dotenv_values(ROOT/'.env')['APP_DATABASE_URL'], connect_timeout=15)

    def test_no_rows_writes_and_multiple_statements_fail_but_next_query_runs(self):
        queries = [
            'SELECT 1 WHERE false',
            'WITH attempted AS (DELETE FROM works WHERE false RETURNING work_id) SELECT * FROM attempted',
            'SELECT 1; SELECT 2',
            "SELECT current_setting('transaction_read_only'),current_user",
        ]
        questions = [dict(id=f'Q{i:02}', category='lookup', reference_sql=sql)
                     for i, sql in enumerate(queries, 1)]
        with self.connect() as conn:
            report = check(conn, questions)
            conn.rollback()
        results = report['results']
        self.assertFalse(report['passed'])
        self.assertEqual(results[0]['reason'], 'empty_result')
        self.assertIn(results[1]['sqlstate'], ('42501', '25006'))
        self.assertEqual(results[2]['reason'], 'sql_error')
        self.assertEqual(results[3]['rows'], [('on','app_reader')])

    def test_no_pending_articles_is_an_explicit_nonempty_answer(self):
        questions = read_questions(ROOT/'evals/golden_questions.csv')
        pending = dict(questions[10])
        # Force an empty candidate set without modifying any source data.
        pending['reference_sql'] = pending['reference_sql'].replace(
            'FROM works w WHERE NOT EXISTS', 'FROM works w WHERE false AND NOT EXISTS')
        with self.connect() as conn:
            report = check(conn, [pending])
            conn.rollback()
        self.assertTrue(report['passed'])
        self.assertEqual(report['results'][0]['rows'], [(0, [])])


if __name__ == '__main__':
    unittest.main()
