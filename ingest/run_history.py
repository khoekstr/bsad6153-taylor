"""Durable run records; successful history commits with the data transaction."""
import uuid

import psycopg
import requests
from psycopg.types.json import Jsonb
from ingest.fetch import FetchError


def safe_error(error):
    # Never store exception strings: URLs, passwords, SQL values or response
    # bodies can be embedded in them. Use only fixed classifications.
    if isinstance(error, (KeyboardInterrupt, SystemExit)):
        return 'Run interrupted; data and progress transaction rolled back.'
    if isinstance(error, (FetchError, requests.RequestException)):
        cause = 'Source request failed (authentication, availability, response format, or retry/request limit).'
    elif isinstance(error, psycopg.IntegrityError):
        cause = 'Database rejected data that violated a constraint.'
    elif isinstance(error, psycopg.OperationalError):
        cause = 'Database connection or operation failed.'
    elif isinstance(error, (ValueError, KeyError, TypeError)):
        cause = 'Configuration or source-data validation failed.'
    elif isinstance(error, OSError):
        cause = 'Local file operation failed.'
    else:
        cause = 'Sync operation failed (including a concurrent-run lock conflict).'
    return cause + ' Data and progress transaction rolled back; sensitive details omitted.'


def run_logged(conn, operation, *, stats, trigger='manual', dry_run=False,
               mode='discovery_only', run_id=None):
    if not conn.autocommit:
        raise ValueError('Run history requires an autocommit connection')
    run_id = run_id or uuid.uuid4()
    # Commit a conservative sentinel before fetching. A hard kill leaves an
    # unfinished failed row rather than silently losing evidence of the attempt.
    conn.execute('''INSERT INTO sync_runs(run_id,status,trigger,dry_run,mode,error_message)
        VALUES (%s,'failed',%s,%s,%s,'Run started; completion not yet recorded.')''',
                 (run_id, trigger, dry_run, mode))
    try:
        with conn.transaction():
            result = operation()
            noop = result.get('status') == 'already_completed_today'
            partial = (not noop and mode == 'discovery_only'
                       and result.get('records_inserted', 0) == 0)
            status = 'partial' if partial else 'success'
            outcome = 'already_completed_today' if noop else 'preview' if dry_run else 'completed'
            error = 'No eligible new papers found within the bounded search.' if partial else None
            inserted = 0 if dry_run else result.get('records_inserted', 0)
            updated = 0 if dry_run else result.get('records_updated', 0)
            # Whitelist numeric counters only; maintenance reasons and arbitrary
            # provider text never enter the audit details.
            details = {key: value for key, value in result.items()
                       if key in ('authorships_inserted','authorships_updated','authorships_removed',
                                  'abstracts_changed','assessment_pending','requests')
                       and type(value) is int}
            if dry_run:
                details.update(proposed_records_inserted=result.get('records_inserted', 0),
                               proposed_records_updated=result.get('records_updated', 0))
            conn.execute('''UPDATE sync_runs SET finished_at=clock_timestamp(),status=%s,
                records_fetched=%s,records_inserted=%s,records_updated=%s,
                error_message=%s,outcome=%s,details=%s WHERE run_id=%s''',
                (status, int(stats.get('records_fetched', 0)), inserted, updated,
                 error, outcome, Jsonb(details), run_id))
        return {**result, 'run_id': str(run_id), 'run_status': status,
                'committed_records_inserted': inserted, 'committed_records_updated': updated}
    except BaseException as error:
        # The outer transaction has rolled back source data, progress and success
        # metadata. The initial run row survives and is finalized separately.
        try:
            conn.execute('''UPDATE sync_runs SET finished_at=clock_timestamp(),status='failed',
                records_fetched=%s,records_inserted=0,records_updated=0,
                error_message=%s,outcome='rolled_back' WHERE run_id=%s AND finished_at IS NULL''',
                (int(stats.get('records_fetched', 0)), safe_error(error), run_id))
        except Exception:
            # If connectivity is gone, retain the committed unfinished sentinel.
            pass
        raise
