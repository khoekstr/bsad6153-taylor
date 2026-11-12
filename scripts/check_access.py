"""Prove app_reader can read but cannot write. No test changes are committed."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
TABLES = {'works': 'title', 'authorships': 'work_id', 'reading_notes': 'work_id',
          'work_assessments': 'work_id', 'work_connections': 'from_work_id',
          'sync_state': 'pipeline', 'sync_runs': 'status'}


def check(conn):
    user = conn.execute('SELECT current_user').fetchone()[0]
    print('Database user:', user)
    if user != 'app_reader':
        print('[FAIL] Refusing permission tests with another role.')
        return 1
    failed = False
    for table, column in TABLES.items():
        query = sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(table))
        print(query.as_string(conn) + ';')
        print('  SELECT succeeded; rows:', conn.execute(query).fetchone()[0])
        privileges = conn.execute(
            "SELECT has_table_privilege(current_user,%s,p) FROM "
            "unnest(ARRAY['INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) p",
            ('public.' + table,),
        ).fetchall()
        if any(row[0] for row in privileges):
            print('[FAIL] Unexpected non-SELECT table privilege:', table)
            failed = True
        # Empty predicates prevent changes even if permissions are incorrect.
        # Rollback provides an additional safeguard; INSERT uses no sequence.
        probes = [
            sql.SQL('DELETE FROM public.{} WHERE false').format(sql.Identifier(table)),
            sql.SQL('INSERT INTO public.{} ({}) SELECT {} FROM public.{} WHERE false').format(
                sql.Identifier(table), sql.Identifier(column), sql.Identifier(column), sql.Identifier(table)),
        ]
        for query in probes:
            print(query.as_string(conn) + ';')
            try:
                with conn.transaction(force_rollback=True):
                    conn.execute(query)
            except psycopg.errors.InsufficientPrivilege:
                print('  permission denied (SQLSTATE 42501) [expected]')
            else:
                print('[FAIL] Write command was permitted; no rows changed.')
                failed = True
    if conn.execute("SELECT has_schema_privilege(current_user,'public','CREATE')").fetchone()[0]:
        print('[FAIL] Unexpected CREATE permission on public schema.')
        failed = True
    print('[FAIL] Access checks failed.' if failed else f'[ok] All {len(TABLES)} tables readable; INSERT and DELETE denied; no changes committed.')
    return int(failed)


def main():
    load_dotenv(ROOT / '.env')
    url = os.environ.get('APP_DATABASE_URL')
    if not url:
        print('[FAIL] APP_DATABASE_URL is not set.')
        return 1
    try:
        with psycopg.connect(url, connect_timeout=10, autocommit=True) as conn:
            return check(conn)
    except Exception as error:
        print('[FAIL] ' + type(error).__name__ + '; connection details omitted for privacy.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
