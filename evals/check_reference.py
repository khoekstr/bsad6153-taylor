"""Validate live SQL reference answers as app_reader; never invoke a sync or AI."""
import argparse
import csv
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
from uuid import UUID

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ['id', 'question', 'category', 'reference_sql', 'correct_behavior', 'source']
CATEGORIES = {'lookup', 'aggregate', 'trend', 'compare', 'should_decline'}


def read_questions(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != FIELDS:
            raise ValueError('CSV headers must match the six assignment columns in order.')
        rows = list(reader)
    if len(rows) < 15:
        raise ValueError('At least 15 questions are required.')
    for index, row in enumerate(rows, 1):
        if set(row) != set(FIELDS) or any(value is None for value in row.values()):
            raise ValueError('Malformed CSV row.')
        if row['id'] != f'Q{index:02}':
            raise ValueError('IDs must be unique and sequential, starting at Q01.')
        if not row['question'].strip() or not row['correct_behavior'].strip():
            raise ValueError('Questions and correct behavior cannot be blank.')
        if row['category'] not in CATEGORIES or row['source'] not in {'baseline', 'other'}:
            raise ValueError('Invalid category or source.')
        sql = row['reference_sql'].strip()
        if row['category'] == 'should_decline':
            if sql:
                raise ValueError('Decline questions must have empty reference SQL.')
        elif not re.match(r'^(SELECT|WITH)\b', sql, flags=re.I):
            raise ValueError('Answerable questions must supply SELECT/WITH SQL.')
    if sum(row['source'] == 'baseline' for row in rows) < 8:
        raise ValueError('At least eight baseline questions are required.')
    if sum(row['category'] == 'should_decline' for row in rows) < 3:
        raise ValueError('At least three decline questions are required.')
    return rows


def json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    raise TypeError('Unsupported database result type.')


def check(conn, questions):
    # One consistent snapshot across all answers, even if a scheduled sync runs.
    conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
    conn.execute("SET LOCAL TIME ZONE 'America/Chicago'")
    conn.execute("SET LOCAL statement_timeout = '30s'")
    conn.execute("SET LOCAL lock_timeout = '5s'")
    conn.execute('SET LOCAL search_path = public, pg_catalog')
    user, session_user, readonly, as_of = conn.execute(
        "SELECT current_user,session_user,current_setting('transaction_read_only'),now()"
    ).fetchone()
    if user != 'app_reader' or session_user != 'app_reader' or readonly != 'on':
        raise ValueError('Connection must be app_reader in a read-only transaction.')
    results = []
    for question in questions:
        result = {'id': question['id'], 'category': question['category']}
        if question['category'] == 'should_decline':
            result['status'] = 'not_executed_should_decline'
        else:
            sql = question['reference_sql']
            result['sql_sha256'] = hashlib.sha256(sql.encode()).hexdigest()
            try:
                # Each query has its own savepoint, so failures do not hide later results.
                # Prepared execution rejects multiple SQL statements in one CSV cell.
                with conn.transaction():
                    cursor = conn.execute(sql, prepare=True)
                    columns = [column.name for column in cursor.description]
                    records = cursor.fetchall()
                    if not records:
                        result.update(status='fail', reason='empty_result', row_count=0)
                    else:
                        result.update(status='pass', columns=columns,
                                      row_count=len(records), rows=records)
            except psycopg.Error as error:
                # Do not expose exception messages, connection details, or query parameters.
                result.update(status='fail', reason='sql_error', sqlstate=error.sqlstate)
        results.append(result)
    return {'format_version': 1, 'as_of': as_of, 'database_user': user,
            'timezone': 'America/Chicago', 'read_only': True,
            'results': results,
            'passed': all(r['status'] != 'fail' for r in results)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--questions', type=Path, default=ROOT/'evals/golden_questions.csv')
    parser.add_argument('--output', type=Path,
                        help='Optional PRIVATE JSON answer snapshot; existing files are never overwritten.')
    parser.add_argument('--validate-only', action='store_true', help='Check CSV structure without connecting.')
    args = parser.parse_args(argv)
    try:
        questions = read_questions(args.questions)
        if args.validate_only:
            print(f'PASS: {len(questions)} questions; CSV requirements met.')
            return 0
        if args.output and args.output.exists():
            print('FAIL: output already exists; choose a new snapshot name.')
            return 1
        load_dotenv(ROOT/'.env')
        url = os.getenv('APP_DATABASE_URL')
        if not url:
            print('FAIL: APP_DATABASE_URL is required. No administrator fallback.')
            return 1
        with psycopg.connect(url, connect_timeout=15) as conn:
            report = check(conn, questions)
            conn.rollback()
        report['questions_sha256'] = hashlib.sha256(args.questions.read_bytes()).hexdigest()
        for result in report['results']:
            suffix = f" ({result['row_count']} rows)" if 'row_count' in result else ''
            if result['status'] == 'fail':
                suffix += ' ' + result['reason'] + ' ' + (result.get('sqlstate') or '')
            print(result['id'] + ': ' + result['status'] + suffix)
        print('Database user: app_reader; read-only; one consistent snapshot.')
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('x', encoding='utf-8') as handle:
                json.dump(report, handle, indent=2, ensure_ascii=False, default=json_value)
                handle.write('\n')
            print('Private answer snapshot saved. It may contain personal notes; do not publish it.')
        print('PASS' if report['passed'] else 'FAIL')
        return 0 if report['passed'] else 1
    except ValueError as error:
        print(f'FAIL: {error}')
    except (psycopg.Error, OSError, csv.Error, TypeError):
        print('FAIL: unable to complete reference check; sensitive error details withheld.')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
