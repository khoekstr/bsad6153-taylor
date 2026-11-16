"""Preview full-article estimates from page ranges; --apply fills missing AI values.

Run db/migrations/003_reading_time_basis.sql before using this script.
No full text is fetched. Existing estimates and user assessments are preserved.
"""
import argparse
import os
from pathlib import Path
import re

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]


def estimate(raw):
    """Use only unambiguous ascending numeric ranges of 2–100 pages."""
    if not isinstance(raw, dict):
        return None
    biblio = raw.get('biblio')
    if not isinstance(biblio, dict):
        return None
    first, last = biblio.get('first_page'), biblio.get('last_page')
    if not all(isinstance(v, str) and re.fullmatch(r'[0-9]{1,5}', v) for v in (first, last)):
        return None
    start, end = int(first), int(last)
    pages = end - start + 1
    # Equal endpoints often represent an article identifier, not a one-page paper.
    if start < 1 or not 2 <= pages <= 100:
        return None
    basis = (f'Full article; OpenAlex page range {first}–{last} ({pages} pages). '
             'Rough estimate: 500 words/page at 250 words/minute = 2 minutes/page, '
             'including references and figures. Not measured full-text length or study time.')
    return pages * 2, basis


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    load_dotenv(ROOT / '.env')
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:
        if not args.apply:
            conn.execute('SET TRANSACTION READ ONLY')
        rows = conn.execute('''SELECT a.assessment_id, w.raw
            FROM work_assessments a JOIN works w ON w.work_id = a.work_id
            WHERE a.assessed_by = 'ai' AND a.estimated_reading_minutes IS NULL''').fetchall()
        candidates = [(aid, result) for aid, raw in rows if (result := estimate(raw))]
        changed = 0
        if args.apply:
            for aid, (minutes, basis) in candidates:
                changed += conn.execute('''UPDATE work_assessments
                    SET estimated_reading_minutes = %s, estimated_reading_basis = %s
                    WHERE assessment_id = %s AND assessed_by = 'ai'
                      AND estimated_reading_minutes IS NULL''',
                    (minutes, basis, aid)).rowcount
        print(f'Missing AI estimates examined: {len(rows)}')
        print(f'Usable page ranges: {len(candidates)}')
        print(f'Left unknown: {len(rows) - len(candidates)}')
        print(f'Rows updated: {changed}' if args.apply else 'Preview only; no changes made.')


if __name__ == '__main__':
    main()
