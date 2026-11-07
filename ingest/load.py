"""Load a reviewed OpenAlex selection; --dry-run never opens a database."""
import argparse
from collections import Counter
from datetime import date
import json
import os
from pathlib import Path
import re
import warnings

ROOT = Path(__file__).resolve().parents[1]


def abstract_text(index):
    if not index:
        return None
    positions = {}
    for word, offsets in index.items():
        for offset in offsets:
            if not isinstance(offset, int) or offset < 0 or offset in positions:
                raise ValueError("Invalid abstract positions")
            positions[offset] = word
    return " ".join(positions[i] for i in sorted(positions)) or None


def prepare(folder):
    manifest = json.loads((folder / 'reviewed_selection.json').read_text(encoding='utf-8-sig'))
    cache, rows = {}, []
    for source_id, provenance in manifest['selected'].items():
        filename = provenance['raw_file']
        path = (folder / filename).resolve()
        if path.parent != folder.resolve():
            raise ValueError('Raw file must be inside the selected run folder')
        if filename not in cache:
            payload = json.loads(path.read_text(encoding='utf-8-sig'))
            cache[filename] = {w['id']: w for w in payload['results']}
        work = cache[filename][source_id]
        if not re.fullmatch(r'https://openalex.org/W[0-9]+', source_id):
            raise ValueError('Invalid work ID')
        title = work.get('display_name')
        if not title or not title.strip() or not work.get('type'):
            raise ValueError('Selected work lacks title or type')
        published = date.fromisoformat(work['publication_date']) if work.get('publication_date') else None
        year = work.get('publication_year')
        if year is not None and (type(year) is not int or not 1 <= year <= 9999):
            raise ValueError('Invalid publication year')
        credits = {}
        for credit in work.get('authorships') or []:
            author = credit.get('author') or {}
            author_id, name = author.get('id'), author.get('display_name')
            if not author_id or not name or not name.strip():
                warnings.warn('Skipped incomplete author credit; original retained in works.raw')
                continue
            if not re.fullmatch(r'https://openalex.org/A[0-9]+', author_id):
                raise ValueError('Invalid author ID')
            position = credit.get('author_position')
            if position not in (None, 'first', 'middle', 'last'):
                raise ValueError('Unexpected author position')
            value = (author_id, name, position)
            if author_id in credits and credits[author_id] != value:
                raise ValueError('Conflicting duplicate author credits')
            credits[author_id] = value
        values = (source_id, title, work.get('doi'), published, year, work['type'],
                  work.get('language'), abstract_text(work.get('abstract_inverted_index')),
                  (work.get('primary_topic') or {}).get('display_name'), provenance.get('group'),
                  (work.get('open_access') or {}).get('is_oa'),
                  (work.get('best_oa_location') or {}).get('pdf_url'))
        rows.append((values, work, list(credits.values())))
    return rows


def load_rows(conn, rows):
    from psycopg.types.json import Jsonb
    added = Counter(works=0, authorships=0)
    for values, raw, credits in rows:
        result = conn.execute('''INSERT INTO works
            (openalex_id,title,doi,publication_date,publication_year,work_type,language,
             abstract,primary_topic,selection_reason,is_open_access,pdf_url,raw)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (openalex_id) DO NOTHING RETURNING work_id''',
            (*values, Jsonb(raw))).fetchone()
        if result:
            added['works'] += 1
        else:
            result = conn.execute('SELECT work_id FROM works WHERE openalex_id=%s',
                                  (values[0],)).fetchone()
        work_id = result[0]
        for credit in credits:
            inserted = conn.execute('''INSERT INTO authorships
                (work_id,author_openalex_id,author_name,author_position)
                VALUES (%s,%s,%s,%s) ON CONFLICT (work_id,author_openalex_id)
                DO NOTHING RETURNING authorship_id''', (work_id, *credit)).fetchone()
            added['authorships'] += bool(inserted)
    return dict(added)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path,
                        default=ROOT / 'data/raw/20261029T155716Z_d357540f')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        rows = prepare(args.run_dir)
        print(json.dumps({'selected_works': len(rows),
                          'authorships': sum(len(r[2]) for r in rows),
                          'missing_abstracts': sum(r[0][7] is None for r in rows),
                          'missing_dates': sum(r[0][3] is None for r in rows),
                          'works_without_credits': sum(not r[2] for r in rows)}))
        if len(rows) < 500:
            raise ValueError('At least 500 selected works are required')
        if args.dry_run:
            print('Dry run passed. No database connection or writes; no notes invented.')
            return 0
        import psycopg
        from dotenv import load_dotenv
        load_dotenv(ROOT / '.env')
        url = os.environ.get('DATABASE_URL')
        if not url:
            print('DATABASE_URL is missing. Student: configure the Session pooler locally.')
            return 1
        with psycopg.connect(url, connect_timeout=10) as conn:
            added = load_rows(conn, rows)
        print('Committed new rows: ' + json.dumps(added))
        print('Existing rows and personal notes were not changed.')
        return 0
    except Exception as error:
        # Database/connection exceptions can contain credentials or personal data.
        print('Load failed (' + type(error).__name__ + '). No partial transaction committed.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
