"""Reproduce Part G scenarios with real PostgreSQL transactions and synthetic data.

Only connection-local TEMP tables are written. No HTTP calls or live syncs occur.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

import psycopg
from psycopg import sql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ingest import sync
from ingest.run_history import run_logged
from ingest.test_sync import FakeClient as BaseFakeClient, page, plan, work


class FakeClient(BaseFakeClient):
    def get(self, endpoint, params):
        payload, filename = super().get(endpoint, params)
        self.stats['requests'] += 1
        self.stats['records_fetched'] += len(payload['results'])
        return payload, filename


@contextmanager
def isolated_database():
    with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True, connect_timeout=15) as conn:
        conn.execute("SET statement_timeout='30s'")
        conn.execute("SET lock_timeout='5s'")
        for table in ('works', 'authorships', 'sync_state', 'sync_runs'):
            conn.execute(sql.SQL('CREATE TEMP TABLE {} (LIKE public.{} INCLUDING ALL)').format(
                sql.Identifier(table), sql.Identifier(table)))
        conn.execute('SET search_path = pg_temp, public')
        conn.execute('ALTER TABLE authorships ADD FOREIGN KEY(work_id) REFERENCES works(work_id)')
        for table in ('works', 'authorships'):
            conn.execute(sql.SQL('CREATE TRIGGER stamp BEFORE UPDATE ON {} FOR EACH ROW '
                                 'EXECUTE FUNCTION public.stamp_last_updated_at()').format(sql.Identifier(table)))
        for table in ('works', 'authorships', 'sync_state', 'sync_runs'):
            namespace = conn.execute(
                'SELECT relnamespace::regnamespace::text FROM pg_class WHERE oid=to_regclass(%s)',
                (table,)).fetchone()[0]
            if not namespace.startswith('pg_temp_'):
                raise RuntimeError('Isolation check failed; refusing to run.')
        # Do not compete with the production pipeline's advisory lock.
        with patch.object(sync, 'LOCK_ID', -6153003):
            yield conn


def counts(conn):
    return dict(zip(('works', 'authorships', 'sync_state', 'duplicate_openalex_ids'), conn.execute(
        '''SELECT (SELECT count(*) FROM works),(SELECT count(*) FROM authorships),
        (SELECT count(*) FROM sync_state),
        (SELECT count(*) FROM (SELECT openalex_id FROM works GROUP BY openalex_id HAVING count(*)>1) d)'''
    ).fetchone()))


def history(conn):
    return [r[0] for r in conn.execute('SELECT to_jsonb(r) FROM sync_runs r ORDER BY started_at,run_id')]


def discovery(conn, record, now):
    client = FakeClient([page([record])])
    return run_logged(conn, lambda: sync.synchronize(conn, client, plan(), now=now),
                      stats=client.stats, trigger='manual')


def rerun():
    prediction = 'First run inserts 1 and updates 0; immediate rerun inserts/updates/fetches 0; one paper and two credits remain.'
    print('RERUN prediction:', prediction)
    with isolated_database() as conn:
        now = datetime.now(timezone.utc)
        first = discovery(conn, work(title='Part G synthetic rerun paper'), now)
        before = counts(conn)
        client = FakeClient([])  # Raises if the daily guard incorrectly requests data.
        second = run_logged(conn, lambda: sync.synchronize(conn, client, plan(), now=now),
                            stats=client.stats, trigger='manual')
        after = counts(conn)
        assert (first['committed_records_inserted'],first['committed_records_updated']) == (1,0)
        assert (second['committed_records_inserted'],second['committed_records_updated']) == (0,0)
        assert second['status'] == 'already_completed_today' and not client.calls
        assert before == after == dict(works=1,authorships=2,sync_state=1,duplicate_openalex_ids=0)
        return dict(test='rerun',prediction=prediction,passed=True,before=before,after=after,rows=history(conn))


def interrupted():
    prediction = 'Interrupt after a write: failed run retains an audit row but no paper, credits, or progress. Recovery inserts 1 and updates 0 without duplicates.'
    print('INTERRUPTION prediction:', prediction)
    with isolated_database() as conn:
        original_upsert = sync.upsert_rows
        observed_inside = {}

        def stop_after_write(*args, **kwargs):
            original_upsert(*args, **kwargs)
            observed_inside.update(counts(conn))
            raise KeyboardInterrupt()

        client = FakeClient([page([work(title='Part G interrupted synthetic paper')])])
        now = datetime.now(timezone.utc)
        try:
            with patch.object(sync, 'upsert_rows', stop_after_write):
                run_logged(conn, lambda: sync.synchronize(conn, client, plan(), now=now),
                           stats=client.stats, trigger='manual')
        except KeyboardInterrupt:
            pass
        else:
            raise AssertionError('Expected interruption did not occur')
        after_failure = counts(conn)
        assert observed_inside['works'] == 1 and observed_inside['authorships'] == 2
        assert after_failure == dict(works=0,authorships=0,sync_state=0,duplicate_openalex_ids=0)
        failed = history(conn)[0]
        assert failed['status']=='failed' and failed['outcome']=='rolled_back'
        assert failed['records_inserted']==failed['records_updated']==0
        assert failed['finished_at'] is not None
        recovered = discovery(conn, work(title='Part G interrupted synthetic paper'), now)
        assert recovered['committed_records_inserted']==1 and recovered['committed_records_updated']==0
        after_recovery = counts(conn)
        assert after_recovery == dict(works=1,authorships=2,sync_state=1,duplicate_openalex_ids=0)
        return dict(test='interrupted_run',prediction=prediction,passed=True,
                    interruption='Injected KeyboardInterrupt after upsert, before transaction commit; not an OS hard kill.',
                    observed_inside_transaction=observed_inside,after_failure=after_failure,
                    after_recovery=after_recovery,rows=history(conn))


def source_change():
    prediction = 'Seed inserts 1. Explicit targeted refresh changes citations 2 to 12 and title, inserts 0, updates 1. Identical refresh updates 0; discovery progress is unchanged.'
    print('SOURCE CHANGE prediction:', prediction)
    with isolated_database() as conn:
        now = datetime.now(timezone.utc)
        record = work(title='Part G source title'); record['cited_by_count'] = 2
        discovery(conn, record, now)
        state_before = conn.execute('SELECT state FROM sync_state WHERE pipeline=%s',(sync.PIPELINE,)).fetchone()[0]
        changed = work(title='Part G corrected source title'); changed['cited_by_count'] = 12
        for expected_updates in (1, 0):
            client = FakeClient([page([changed])])
            result = run_logged(conn, lambda: sync.refresh_one(conn,client,changed['id'],
                                'Part G synthetic source-change test'), stats=client.stats,
                                trigger='manual',mode='targeted_refresh')
            assert result['committed_records_inserted']==0
            assert result['committed_records_updated']==expected_updates
        assert conn.execute('SELECT title,cited_by_count FROM works').fetchone() == ('Part G corrected source title',12)
        assert conn.execute('SELECT state FROM sync_state WHERE pipeline=%s',(sync.PIPELINE,)).fetchone()[0] == state_before
        after = counts(conn)
        assert after['works']==1 and after['duplicate_openalex_ids']==0 and after['authorships']==2
        return dict(test='source_change',prediction=prediction,passed=True,after=after,
                    before_source=dict(title=record['display_name'],cited_by_count=2),
                    after_source=dict(title=changed['display_name'],cited_by_count=12),
                    discovery_state_unchanged=True,rows=history(conn))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; choose a new evidence filename.')
    load_dotenv(ROOT/'.env')
    report = dict(started_at=datetime.now(timezone.utc).isoformat(),
                  scope='Connection-local PostgreSQL TEMP tables; synthetic source responses; no HTTP requests; production run history untouched.')
    try:
        report['tests'] = [rerun(),interrupted(),source_change()]
        report['passed'] = True
    except (Exception, KeyboardInterrupt):
        print('FAIL: controlled scenario did not complete; sensitive exception details withheld.')
        return 1
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as handle:
        json.dump(report,handle,indent=2); handle.write('\n')
    print('PASS: three scenarios; seven temporary sync_runs rows saved as evidence.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
