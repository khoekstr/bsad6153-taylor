"""Bounded OpenAlex sync. No LLM calls; new works remain assessment-pending.

Run from any folder: python ingest/sync.py --dry-run
Apply migrations 005 (sync_state) and 006 (sync_runs) before running.
"""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone, date
import hashlib
import json
import logging
import os
import re
from pathlib import Path
import sys
import uuid

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from ingest.fetch import Client, FetchError, normalized, write_json
from ingest.load import prepare_record, abstract_text
from ingest.run_history import run_logged

PIPELINE = 'openalex_library'
LOCK_ID = 6153003
COLUMNS = ('openalex_id', 'title', 'doi', 'publication_date', 'publication_year',
           'work_type', 'language', 'abstract', 'openalex_topic', 'is_open_access',
           'pdf_url', 'source_url', 'raw')


def preferences(path):
    plan = json.loads(path.read_text(encoding='utf-8'))
    for key, low, high in [('max_additions', 1, 5),
                           ('max_requests', 1, 100), ('max_pages_per_topic', 1, 5)]:
        if type(plan.get(key)) is not int or not low <= plan[key] <= high:
            raise ValueError('Invalid preference: ' + key)
    if plan.get('sync_filter_access') not in ('free', 'paid'):
        raise ValueError('sync_filter_access must be free or paid')
    if not isinstance(plan.get('topics'), list) or len(plan['topics']) > 10:
        raise ValueError('At most ten general search topics are allowed')
    for topic in plan['topics']:
        if (not isinstance(topic.get('query'), str) or not topic['query'].strip()
                or len(topic['query']) > 200 or type(topic.get('enabled')) is not bool
                or type(topic.get('priority')) is not int):
            raise ValueError('Invalid general search topic')
        if not isinstance(topic.get('match_terms', []), list) or any(
                not isinstance(t, str) or not t.strip() for t in topic.get('match_terms', [])):
            raise ValueError('Topic match_terms must be nonempty strings')
    if not isinstance(plan.get('excluded_terms'), list) or any(
            not isinstance(t, str) or not t.strip() for t in plan['excluded_terms']):
        raise ValueError('Excluded terms must be nonempty strings')
    return plan


def fingerprint(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()


def doi_key(value):
    return (value or '').lower().strip().removeprefix('https://doi.org/').removeprefix('http://doi.org/').removeprefix('doi:')


def blocked(record, plan):
    text = normalized(' '.join([record.get('display_name') or '',
                               abstract_text(record.get('abstract_inverted_index')) or '',
                               (record.get('primary_topic') or {}).get('display_name') or '']))
    # Paused topics are also excluded from fallback using their editable terms.
    terms = plan['excluded_terms'] + [term for topic in plan['topics'] if not topic['enabled']
                                      for term in topic.get('match_terms', [topic['query']])]
    return any(normalized(term) in text for term in terms)


def eligible(record, plan, today):
    if record.get('language') != 'en' or (record.get('open_access') or {}).get('is_oa') is not True:
        return False
    published = record.get('publication_date')
    return bool(published and date.fromisoformat(published) <= today and not blocked(record, plan))


def discover(client, known, state, plan, today):
    ids = set(known)
    dois = {doi_key(v[0]) for v in known.values() if doi_key(v[0])}
    titles = {normalized(v[1]) for v in known.values()}
    chosen = []
    cursors = state.setdefault('discovery_cursors', {})

    def query_topic(query, limit):
        filters = 'language:en,is_oa:true,to_publication_date:' + today.isoformat()
        if (query and plan['sync_filter_access'] == 'paid' and state.get('last_success_at')
                and state.get('preferences_sha256') == fingerprint(plan)):
            filters += ',from_updated_date:' + state['last_success_at'][:10]
        params = {'filter': filters, 'sort': 'publication_date:desc', 'per_page': 100}
        if query:
            params['search'] = query
        key = query or '__fallback__'
        # Always examine the newest page. Also walk older results across days;
        # publication time is not claimed to be a source-update watermark.
        cursor = '*'
        candidates = {}
        for page in range(plan['max_pages_per_topic']):
            payload, _ = client.get('works', {**params, 'cursor': cursor})
            for record in payload['results']:
                if record.get('id') in ids:
                    continue  # Existing search hits are ignored without reviewing their metadata.
                prepare_record(record)  # Validate new candidates only.
                candidates[record['id']] = record
            next_cursor = (payload.get('meta') or {}).get('next_cursor')
            if not next_cursor or not payload['results']:
                cursors[key] = '*'
                break
            saved = cursors.get(key)
            cursor = saved if page == 0 and saved and saved != '*' else next_cursor
            cursors[key] = next_cursor
        for record in sorted(candidates.values(), key=lambda r: (r.get('publication_date') or '', r['id']), reverse=True):
            identifier = record['id']
            doi, title = doi_key(record.get('doi')), normalized(record['display_name'])
            if identifier in ids or (doi and doi in dois) or title in titles or not eligible(record, plan, today):
                continue
            chosen.append(record)
            ids.add(identifier)
            titles.add(title)
            if doi:
                dois.add(doi)
            if len(chosen) >= limit:
                break

    for topic in sorted(plan['topics'], key=lambda t: (t['priority'], t['query'])):
        if topic['enabled'] and len(chosen) < plan['max_additions']:
            query_topic(topic['query'], plan['max_additions'])
    if not chosen:
        # The any-category fallback supplies one, not five unrelated fillers.
        query_topic(None, 1)
    return chosen


def upsert_rows(conn, records, *, allow_updates=False):
    counts = {'records_inserted': 0, 'records_updated': 0,
              'authorships_inserted': 0, 'authorships_updated': 0, 'authorships_removed': 0,
              'abstracts_changed': 0, 'abstract_changed_ids': []}
    cols = sql.SQL(',').join(map(sql.Identifier, COLUMNS))
    updates = sql.SQL(',').join(sql.SQL('{}=EXCLUDED.{}').format(sql.Identifier(c), sql.Identifier(c)) for c in COLUMNS[1:])
    # Source updated_date and query relevance are transport metadata, not edits
    # to library content. All other raw source changes are retained and counted.
    left = sql.SQL(',').join(sql.SQL('works.{}').format(sql.Identifier(c)) for c in COLUMNS[1:-1])
    right = sql.SQL(',').join(sql.SQL('EXCLUDED.{}').format(sql.Identifier(c)) for c in COLUMNS[1:-1])
    statement = sql.SQL('''INSERT INTO works AS works ({cols},source)
        VALUES ({args},'openalex') ON CONFLICT (openalex_id) DO UPDATE SET {updates}
        WHERE works.source='openalex' AND
        ROW({left}, works.raw - 'updated_date' - 'relevance_score') IS DISTINCT FROM
        ROW({right}, EXCLUDED.raw - 'updated_date' - 'relevance_score')
        RETURNING work_id''').format(
        cols=cols, args=sql.SQL(',').join([sql.Placeholder()] * len(COLUMNS)), updates=updates, left=left, right=right)
    if not allow_updates:
        statement = sql.SQL('''INSERT INTO works ({cols},source) VALUES ({args},'openalex')
            ON CONFLICT (openalex_id) DO NOTHING RETURNING work_id''').format(
                cols=cols, args=sql.SQL(',').join([sql.Placeholder()] * len(COLUMNS)))
    for record in records:
        values, raw, credits = prepare_record(record)
        before = conn.execute('SELECT work_id,abstract,source FROM works WHERE openalex_id=%s FOR UPDATE', (values[0],)).fetchone()
        if before and (not allow_updates or before[2] != 'openalex'):
            continue  # A manually maintained reference is not owned by this pipeline.
        row = conn.execute(statement, (*values, Jsonb(raw))).fetchone()
        if not allow_updates and not row:
            continue  # Another importer may have inserted it since discovery.
        if row:
            counts['records_updated' if before else 'records_inserted'] += 1
        work_id = before[0] if before else row[0]
        if before and before[1] != values[7]:
            counts['abstracts_changed'] += 1
            counts['abstract_changed_ids'].append(values[0])
        previous = {a[0]: (a[1], a[2]) for a in conn.execute(
            'SELECT author_openalex_id,author_name,author_order FROM authorships WHERE work_id=%s', (work_id,))}
        desired = {a[0]: (a[1], a[2]) for a in credits}
        if previous == desired:
            continue
        # Release moved positions first, avoiding the unique(work_id,author_order)
        # conflict when two existing authors swap order. All steps share a transaction.
        changed = [key for key in previous if key in desired and previous[key] != desired[key]]
        removed = [key for key in previous if key not in desired]
        for key in removed:
            conn.execute('DELETE FROM authorships WHERE work_id=%s AND author_openalex_id IS NOT DISTINCT FROM %s', (work_id, key))
        for key in changed:
            conn.execute('UPDATE authorships SET author_order=NULL WHERE work_id=%s AND author_openalex_id=%s', (work_id, key))
        for author_id, name, order in credits:
            if author_id in previous and author_id not in changed:
                continue
            conn.execute('''INSERT INTO authorships(work_id,author_openalex_id,author_name,author_order)
                VALUES (%s,%s,%s,%s) ON CONFLICT(work_id,author_openalex_id) DO UPDATE
                SET author_name=EXCLUDED.author_name,author_order=EXCLUDED.author_order
                WHERE (authorships.author_name,authorships.author_order) IS DISTINCT FROM
                      (EXCLUDED.author_name,EXCLUDED.author_order)''', (work_id,author_id,name,order))
        counts['authorships_inserted'] += len(desired.keys() - previous.keys())
        counts['authorships_updated'] += len(changed)
        counts['authorships_removed'] += len(removed)
    return counts


def synchronize(conn, client, plan, *, dry_run=False, now=None):
    now = now or datetime.now(timezone.utc)
    # UTC defines the pipeline day consistently on Windows and GitHub runners.
    today = now.date()
    with conn.transaction(force_rollback=dry_run):
        conn.execute("SET LOCAL lock_timeout='5s'")
        conn.execute("SET LOCAL statement_timeout='30s'")
        if not conn.execute('SELECT pg_try_advisory_xact_lock(%s)', (LOCK_ID,)).fetchone()[0]:
            raise RuntimeError('Another sync is running')
        row = conn.execute('SELECT state FROM sync_state WHERE pipeline=%s FOR UPDATE', (PIPELINE,)).fetchone()
        state = deepcopy(row[0]) if row else {}
        if state.get('last_completed_day') == today.isoformat():
            return {'status': 'already_completed_today', 'records_fetched': 0,
                    'records_inserted': 0, 'records_updated': 0, 'dry_run': dry_run}
        if state.get('preferences_sha256') != fingerprint(plan) or plan['sync_filter_access'] == 'paid':
            state['discovery_cursors'] = {}
        known = {r[0] or 'manual:' + str(r[3]): (r[1], r[2]) for r in conn.execute(
            'SELECT openalex_id,doi,title,work_id FROM works')}
        new = discover(client, known, state, plan, today)
        records = new
        counts = upsert_rows(conn, records)
        # Data, cursor, date gate, and watermark commit together, never before writes.
        state.update(last_success_at=now.isoformat(), last_completed_day=today.isoformat(),
                     preferences_sha256=fingerprint(plan),
                     last_added_ids=[r['id'] for r in new])
        summary = {'status': 'success', 'dry_run': dry_run, **counts,
                   'records_fetched': client.stats['records_fetched'],
                   'requests': client.stats['requests'], 'mode': 'discovery_only',
                   'assessment_pending': len(new), 'sync_filter_access': plan['sync_filter_access']}
        state['last_result'] = summary
        state['assessment_stale_ids'] = sorted(set(state.get('assessment_stale_ids', []))
                                              | set(counts['abstract_changed_ids']))
        conn.execute('''INSERT INTO sync_state(pipeline,state) VALUES (%s,%s)
            ON CONFLICT(pipeline) DO UPDATE SET state=EXCLUDED.state,last_updated_at=now()''',
                     (PIPELINE, Jsonb(state)))
        return summary


def refresh_one(conn, client, identifier, reason, *, dry_run=False):
    """Explicit, reason-required maintenance of one existing OpenAlex article."""
    if not re.fullmatch(r'https://openalex.org/W[0-9]+', identifier) or not reason.strip():
        raise ValueError('One full OpenAlex work ID and a reason are required')
    with conn.transaction(force_rollback=dry_run):
        conn.execute("SET LOCAL lock_timeout='5s'")
        conn.execute("SET LOCAL statement_timeout='30s'")
        if not conn.execute('SELECT pg_try_advisory_xact_lock(%s)', (LOCK_ID,)).fetchone()[0]:
            raise RuntimeError('Another sync is running')
        existing = conn.execute("SELECT work_id FROM works WHERE openalex_id=%s AND source='openalex' FOR UPDATE", (identifier,)).fetchone()
        if not existing:
            raise ValueError('Targeted refresh requires an existing OpenAlex article')
        payload, _ = client.get('works', {'filter': 'openalex_id:' + identifier, 'per_page': 1})
        if len(payload['results']) != 1 or payload['results'][0].get('id') != identifier:
            raise FetchError('Requested article not returned; existing record left unchanged')
        counts = upsert_rows(conn, payload['results'], allow_updates=True)
        result = {'status': 'success', 'mode': 'targeted_refresh', 'dry_run': dry_run,
                  'article_id': identifier, 'reason': reason.strip(), **counts,
                  'records_fetched': client.stats['records_fetched'], 'requests': client.stats['requests']}
        # Separate maintenance state never consumes or advances discovery progress.
        conn.execute("""INSERT INTO sync_state(pipeline,state) VALUES (%s,%s)
            ON CONFLICT(pipeline) DO UPDATE SET state=EXCLUDED.state,last_updated_at=now()""",
            ('refresh:' + identifier, Jsonb(result)))
        return result


class SyncClient(Client):
    def get(self, endpoint, params=None):
        payload, filename = super().get(endpoint, params)
        self.stats['records_fetched'] += len(payload['results'])
        return payload, filename


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preferences', type=Path, default=ROOT / 'ingest/search_preferences.json')
    parser.add_argument('--dry-run', action='store_true', help='Fetch and validate, then roll back data and progress')
    parser.add_argument('--refresh-id', help='Explicitly refresh ONE existing full OpenAlex work ID')
    parser.add_argument('--reason', help='Required for targeted refresh; stored locally, not sent to OpenAlex')
    parser.add_argument('--trigger', choices=('manual','schedule'), default='manual')
    args = parser.parse_args()
    if bool(args.refresh_id) != bool(args.reason and args.reason.strip()):
        parser.error('--refresh-id and a nonempty --reason must be supplied together')
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    folder = None
    run_id = uuid.uuid4()
    stats = Counter()
    result = None
    try:
        load_dotenv(ROOT / '.env')
        url = os.getenv('DATABASE_URL')
        if not url:
            raise ValueError('DATABASE_URL is required')
        folder = ROOT / 'data/raw' / ('sync_' + str(run_id))

        def operation(conn):
            folder.mkdir(parents=True)
            plan = preferences(args.preferences)
            key = os.getenv('OPENALEX_API_KEY')
            if not key:
                raise ValueError('OPENALEX_API_KEY is required')
            write_json(folder / 'preferences.json', plan)
            client = SyncClient(key, folder, max_requests=plan['max_requests'])
            client.stats = stats
            if args.refresh_id:
                return refresh_one(conn, client, args.refresh_id, args.reason, dry_run=args.dry_run)
            return synchronize(conn, client, plan, dry_run=args.dry_run)

        with psycopg.connect(url, connect_timeout=15, autocommit=True) as conn:
            result = run_logged(conn, lambda: operation(conn), stats=stats,
                                trigger=args.trigger, dry_run=args.dry_run,
                                mode='targeted_refresh' if args.refresh_id else 'discovery_only',
                                run_id=run_id)
    except (Exception, KeyboardInterrupt) as error:
        result = {'status': 'failed', 'run_id': str(run_id),
                  'error_message': 'Sync failed. No exception details printed. Check sync_runs; if the database was unreachable, its row could not be written.'}
    # Local artifact errors must never relabel a successfully committed run.
    if folder:
        try:
            write_json(folder / 'summary.json', result)
        except OSError:
            print('Local summary could not be saved; database run status is authoritative.')
    print(json.dumps(result, sort_keys=True))
    if args.dry_run:
        print('Preview data/progress rolled back; run-history row retained. Sequence gaps are possible.')
    return 1 if result.get('status') == 'failed' or result.get('run_status') == 'partial' else 0


if __name__ == '__main__':
    raise SystemExit(main())
