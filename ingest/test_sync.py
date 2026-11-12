"""Offline tests plus opt-in PostgreSQL tests in connection-local temporary tables.
Set SYNC_TEST_DATABASE=1 to use DATABASE_URL; no persistent test rows are created.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path
import unittest
from unittest.mock import Mock

from ingest.sync import (ROOT, preferences, discover, refresh_one, synchronize, upsert_rows)


def work(number=1, title='Example paper', authors=(1, 2)):
    return {'id': f'https://openalex.org/W{number}', 'display_name': title,
            'type': 'article', 'publication_date': '2026-11-01', 'publication_year': 2026,
            'language': 'en', 'open_access': {'is_oa': True},
            'abstract_inverted_index': {'Evidence': [0]},
            'authorships': [{'author': {'id': f'https://openalex.org/A{a}', 'display_name': f'Author {a}'}}
                           for a in authors], 'updated_date': '2026-11-01T00:00:00'}


class FakeClient:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.calls = []
        self.stats = Counter()

    def get(self, endpoint, params):
        self.calls.append(params)
        payload = next(self.pages)
        self.stats['requests'] += 1
        self.stats['records_fetched'] += len(payload['results'])
        return payload, 'fake.json'


def page(records, cursor=None):
    return {'results': records, 'meta': {'next_cursor': cursor}}


def plan():
    result = preferences(ROOT / 'ingest/search_preferences.json')
    result['topics'] = [{'query': 'AI learning', 'priority': 1, 'enabled': True}]
    return result


class SelectionTests(unittest.TestCase):
    def test_five_cap_known_ids_dois_titles_and_hard_filters(self):
        records = [work(i, f'Paper {i}') for i in range(1, 12)]
        records[1]['language'] = 'fr'
        records[2]['open_access']['is_oa'] = False
        records[3]['doi'] = 'https://doi.org/10.1/known'
        records[4]['publication_date'] = '2099-01-01'
        known = {'https://openalex.org/W1': ('10.1/known', 'Other title')}
        chosen = discover(FakeClient([page(records)]), known, {}, plan(), datetime(2026,11,11).date())
        self.assertEqual([r['id'] for r in chosen], [f'https://openalex.org/W{i}' for i in [9,8,7,6,11]])
        self.assertLessEqual(len(chosen), 5)

    def test_fallback_one_and_excluded_terms(self):
        p = plan()
        p['excluded_terms'] = ['parenting']
        c = FakeClient([page([]), page([work(1,'AI parenting'),work(2,'Biology')])])
        result = discover(c, {}, {}, p, datetime(2026,11,11).date())
        self.assertEqual([r['id'] for r in result], ['https://openalex.org/W2'])
        self.assertNotIn('search', c.calls[-1])

    def test_priority_before_date_and_paused_query(self):
        p = plan()
        p['topics'].insert(0, {'query':'paused','priority':0,'enabled':False})
        c = FakeClient([page([work(i, f'Paper {i}') for i in range(1,8)])])
        discover(c, {}, {}, p, datetime(2026,11,11).date())
        self.assertEqual(len(c.calls),1)
        self.assertEqual(c.calls[0]['search'],'AI learning')

    def test_paused_subject_excluded_from_fallback(self):
        p=plan()
        p['topics']=[{'query':'AI parenting','priority':1,'enabled':False,'match_terms':['parenting']}]
        chosen=discover(FakeClient([page([work(1,'Parenting tools'),work(2,'Biology')])]),{}, {},p,datetime(2026,11,11).date())
        self.assertEqual([r['id'] for r in chosen],['https://openalex.org/W2'])

    def test_backfill_cursor_resumed(self):
        state={'discovery_cursors':{'AI learning':'saved'}}
        c=FakeClient([page([],None),page([work()],None)])
        # An empty recent page exhausts that search; fallback then supplies one.
        self.assertEqual(len(discover(c,{},state,plan(),datetime(2026,11,11).date())),1)
        self.assertEqual(state['discovery_cursors']['AI learning'],'*')
        c=FakeClient([page([work()], 'recent'),page([work(2)], 'older')])
        state={'discovery_cursors':{'AI learning':'saved'}}
        discover(c,{},state,plan(),datetime(2026,11,11).date())
        self.assertEqual(c.calls[1]['cursor'],'saved')
        self.assertEqual(state['discovery_cursors']['AI learning'],'older')


@unittest.skipUnless(os.getenv('SYNC_TEST_DATABASE')=='1','set SYNC_TEST_DATABASE=1 for isolated database tests')
class DatabaseTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        from dotenv import dotenv_values
        self.conn=psycopg.connect(dotenv_values(ROOT/'.env')['DATABASE_URL'],autocommit=True,connect_timeout=15)
        self.addCleanup(self.conn.close)
        self.conn.execute('CREATE TEMP TABLE works (LIKE public.works INCLUDING ALL)')
        self.conn.execute('CREATE TEMP TABLE authorships (LIKE public.authorships INCLUDING ALL)')
        self.conn.execute('ALTER TABLE authorships ADD FOREIGN KEY(work_id) REFERENCES works(work_id)')
        self.conn.execute("CREATE TEMP TABLE sync_state(pipeline text PRIMARY KEY,state jsonb NOT NULL,last_updated_at timestamptz DEFAULT now())")
        for table in ('works','authorships'):
            self.conn.execute(f'CREATE TRIGGER stamp BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION public.stamp_last_updated_at()')
        self.assertEqual(self.conn.execute("SELECT relnamespace::regnamespace::text FROM pg_class WHERE oid='works'::regclass").fetchone()[0][:7],'pg_temp')

    def test_insert_replay_changed_source_and_authors(self):
        with self.conn.transaction():
            first=upsert_rows(self.conn,[work()])
        self.assertEqual(first['records_inserted'],1)
        stamp=self.conn.execute('SELECT last_updated_at FROM works').fetchone()[0]
        with self.conn.transaction():
            replay=work(); replay['updated_date']='2026-11-10'; replay['relevance_score']=9
            second=upsert_rows(self.conn,[replay])
        self.assertEqual(second['records_updated'],0)
        self.assertEqual(self.conn.execute('SELECT last_updated_at FROM works').fetchone()[0],stamp)
        with self.conn.transaction():
            changed=work(title='Changed',authors=(2,1,3))
            changed['abstract_inverted_index']={'New':[0]}
            counts=upsert_rows(self.conn,[changed],allow_updates=True)
        self.assertEqual(counts['records_updated'],1)
        self.assertEqual(counts['abstracts_changed'],1)
        self.assertEqual(counts['abstract_changed_ids'],['https://openalex.org/W1'])
        self.assertEqual(counts['authorships_updated'],2)
        self.assertEqual(counts['authorships_inserted'],1)
        self.assertGreater(self.conn.execute('SELECT last_updated_at FROM works').fetchone()[0],stamp)
        self.assertEqual(self.conn.execute('SELECT author_openalex_id FROM authorships ORDER BY author_order').fetchall(),[(f'https://openalex.org/A{i}',) for i in (2,1,3)])
        with self.conn.transaction():
            self.assertEqual(upsert_rows(self.conn,[changed],allow_updates=True)['records_updated'],0)

    def test_failure_rolls_back_everything(self):
        bad=work(2); bad['publication_year']=-1
        with self.assertRaises(ValueError):
            with self.conn.transaction():
                upsert_rows(self.conn,[work(),bad])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM works').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM authorships').fetchone()[0],0)

    def test_sync_daily_gate_and_atomic_state(self):
        c=FakeClient([page([work()])])
        now=datetime(2026,11,11,12,tzinfo=timezone.utc)
        result=synchronize(self.conn,c,plan(),now=now)
        self.assertEqual(result['records_inserted'],1)
        replay=synchronize(self.conn,FakeClient([]),plan(),now=now)
        self.assertEqual(replay['records_inserted'],0)
        self.assertEqual(replay['records_fetched'],0)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM sync_state').fetchone()[0],1)

    def test_dry_run_rolls_back_data_and_state(self):
        result=synchronize(self.conn,FakeClient([page([work()])]),plan(),dry_run=True,
                           now=datetime(2026,11,11,12,tzinfo=timezone.utc))
        self.assertEqual(result['records_inserted'],1)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM works').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM sync_state').fetchone()[0],0)

    def test_manual_reference_title_is_not_added_again(self):
        self.conn.execute("INSERT INTO works(source,title,file_path) VALUES ('upload','Manual title','fixture-only.txt')")
        c=FakeClient([page([work(2,'Manual title'),work(3,'Other paper')])])
        result=synchronize(self.conn,c,plan(),now=datetime(2026,11,11,12,tzinfo=timezone.utc))
        self.assertEqual(result['records_inserted'],1)
        self.assertEqual(self.conn.execute('SELECT title FROM works ORDER BY work_id').fetchall(),
                         [('Manual title',),('Other paper',)])

    def test_network_failure_does_not_advance_state(self):
        client=Mock(); client.get.side_effect=RuntimeError('simulated outage')
        with self.assertRaises(RuntimeError):
            synchronize(self.conn,client,plan())
        self.assertEqual(self.conn.execute('SELECT count(*) FROM sync_state').fetchone()[0],0)

    def test_discovery_never_refreshes_or_edits_existing_article(self):
        with self.conn.transaction():
            upsert_rows(self.conn,[work()])
        before=self.conn.execute('SELECT row_to_json(w) FROM works w').fetchone()[0]
        credits=self.conn.execute('SELECT row_to_json(a) FROM authorships a ORDER BY authorship_id').fetchall()
        # Even malformed changed metadata on an existing search hit is ignored.
        changed=work(title='Changed source',authors=(2,)); changed['publication_year']=-1
        c=FakeClient([page([changed,work(2,'New paper')])])
        result=synchronize(self.conn,c,plan(),now=datetime(2026,11,12,12,tzinfo=timezone.utc))
        self.assertEqual(result['records_updated'],0)
        self.assertEqual(result['records_inserted'],1)
        self.assertTrue(all('openalex_id:' not in call['filter'] for call in c.calls))
        self.assertEqual(self.conn.execute('SELECT row_to_json(w) FROM works w WHERE openalex_id=%s',('https://openalex.org/W1',)).fetchone()[0],before)
        self.assertEqual(self.conn.execute('SELECT row_to_json(a) FROM authorships a WHERE work_id=%s ORDER BY authorship_id',(before['work_id'],)).fetchall(),credits)
        with self.conn.transaction():
            self.assertEqual(upsert_rows(self.conn,[work(title='Another change')])['records_updated'],0)

    def test_refresh_requires_target_reason_and_preserves_discovery_state(self):
        with self.conn.transaction():
            upsert_rows(self.conn,[work(),work(2,'Untouched')])
        with self.assertRaises(ValueError):
            refresh_one(self.conn,FakeClient([]),'https://openalex.org/W1','')
        with self.assertRaises(ValueError):
            refresh_one(self.conn,FakeClient([]),'https://openalex.org/W999','Check a broken link')
        c=FakeClient([page([work(title='Requested correction')])])
        result=refresh_one(self.conn,c,'https://openalex.org/W1','Check a source correction')
        self.assertEqual(result['records_updated'],1)
        self.assertEqual(len(c.calls),1)
        self.assertEqual(c.calls[0]['filter'],'openalex_id:https://openalex.org/W1')
        self.assertEqual(self.conn.execute("SELECT title FROM works WHERE openalex_id='https://openalex.org/W2'").fetchone()[0],'Untouched')
        self.assertEqual(self.conn.execute("SELECT pipeline FROM sync_state").fetchall(),[('refresh:https://openalex.org/W1',)])


if __name__=='__main__':
    unittest.main()
