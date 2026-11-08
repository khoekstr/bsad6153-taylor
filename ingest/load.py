"""Load a reviewed OpenAlex selection; --dry-run never opens a database."""
import argparse
from datetime import date
import json
import hashlib
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
        for author_order, credit in enumerate(work.get('authorships') or [], start=1):
            author = credit.get('author') or {}
            author_id, name = author.get('id'), author.get('display_name')
            if not author_id or not name or not name.strip():
                warnings.warn('Skipped incomplete author credit; original retained in works.raw')
                continue
            if not re.fullmatch(r'https://openalex.org/A[0-9]+', author_id):
                raise ValueError('Invalid author ID')
            value = (author_id, name, author_order)
            if author_id in credits:
                if credits[author_id][1] != name:
                    raise ValueError('Conflicting duplicate author credits')
                continue  # Keep the first credited order for a repeated source ID.
            credits[author_id] = value
        values = (source_id, title, work.get('doi'), published, year, work['type'],
                  work.get('language'), abstract_text(work.get('abstract_inverted_index')),
                  (work.get('primary_topic') or {}).get('display_name'),
                  (work.get('open_access') or {}).get('is_oa'),
                  (work.get('best_oa_location') or {}).get('pdf_url'),
                  (work.get('primary_location') or {}).get('landing_page_url'))
        rows.append((values, work, list(credits.values())))
    return rows


def load_rows(conn, rows):
    from psycopg.types.json import Jsonb
    # Batch parents first, then children; executemany binds each row independently.
    with conn.cursor() as cur:
        cur.executemany('''INSERT INTO works
            (openalex_id,title,doi,publication_date,publication_year,work_type,language,
             abstract,openalex_topic,is_open_access,pdf_url,source_url,raw,source)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'openalex')
            ON CONFLICT (openalex_id) DO NOTHING''',
            [(*values, Jsonb(raw)) for values, raw, _ in rows])
        added = {'works': cur.rowcount, 'authorships': 0}
        ids = dict(conn.execute('SELECT openalex_id,work_id FROM works WHERE openalex_id = ANY(%s)',
                               ([v[0] for v, _, _ in rows],)).fetchall())
        credits = [(ids[v[0]], *credit) for v, _, cs in rows for credit in cs]
        if credits:
            cur.executemany('''INSERT INTO authorships
                (work_id,author_openalex_id,author_name,author_order)
                VALUES (%s,%s,%s,%s) ON CONFLICT (work_id,author_openalex_id)
                DO NOTHING''', credits)
            added['authorships'] = cur.rowcount
    return added



def prepare_assessments(path, rows):
    """Read approved chat output, verifying it matches the abstract actually loaded."""
    if path is None:
        return []
    batch = json.loads(path.read_text(encoding='utf-8'))
    if batch.get('status') != 'approved' or not batch.get('pilot_id'):
        raise ValueError('Assessment batch must be approved and have an ID')
    works = {v[0]: v for v, _, _ in rows}
    result, seen = [], set()
    for record in batch['records']:
        source_id = record['openalex_id']
        if source_id in seen:
            raise ValueError('Duplicate assessment in batch')
        seen.add(source_id)
        abstract = works[source_id][7]
        if not abstract or hashlib.sha256(abstract.encode()).hexdigest() != record['abstract_sha256']:
            raise ValueError('Assessment abstract does not match source')
        assessment = record['assessment']
        if assessment['assessed_by'] != 'ai' or assessment['review_basis'] != 'abstract':
            raise ValueError('Expected abstract-only AI assessment')
        if any(assessment.get(k) is not None for k in ('is_favorite', 'reading_status', 'come_back_to_it')):
            raise ValueError('AI assessment cannot set personal controls')
        import_key = batch['pilot_id'] + ':' + source_id
        result.append((import_key, source_id, record['abstract_sha256'], assessment))
    return result


def load_assessments(conn, assessments):
    added = 0
    for import_key, source_id, abstract_hash, a in assessments:
        work = conn.execute('SELECT work_id, abstract FROM works WHERE openalex_id=%s',
                            (source_id,)).fetchone()
        if not work or not work[1] or hashlib.sha256(work[1].encode()).hexdigest() != abstract_hash:
            raise ValueError('Stored work does not match reviewed abstract')
        inserted = conn.execute('''INSERT INTO work_assessments
            (import_key,work_id,assessed_by,categories,value_rating,value_reason,summary,
             relevance_reason,novelty_rating,novelty_reason,evidence_assessment,
             estimated_reading_minutes,review_basis,assessment_context,assessment_reason,model_used)
            VALUES (%s,%s,'ai',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (import_key) DO NOTHING RETURNING assessment_id''',
            (import_key,work[0],a['categories'],a['value_rating'],a['value_reason'],
             a['summary'],a['relevance_reason'],a['novelty_rating'],a['novelty_reason'],
             a['evidence_assessment'],a['estimated_reading_minutes'],a['review_basis'],
             a['assessment_context'],a['assessment_reason'],a['model_used'])).fetchone()
        added += bool(inserted)
    return added


def prepare_connections(path, rows):
    """Validate saved AI suggestions and both source abstracts; no review gate."""
    if path is None:
        return []
    batch = json.loads(path.read_text(encoding='utf-8'))
    if not batch.get('batch_id'):
        raise ValueError('Connection batch needs provenance')
    sources = {v[0]: v[7] for v, _, _ in rows}
    result, seen = [], set()
    allowed = {'supports', 'challenges', 'extends', 'overlaps', 'related_topic'}
    for record in batch['records']:
        source, target = record['from_openalex_id'], record['to_openalex_id']
        kind = record['connection_type']
        if source == target or kind not in allowed:
            raise ValueError('Invalid connection endpoints or type')
        if (record['proposed_by'], record['review_basis'], record['review_status']) != ('ai', 'abstract', 'suggested'):
            raise ValueError('Expected an abstract-only AI suggestion')
        for side, identifier in (('from', source), ('to', target)):
            abstract = sources.get(identifier)
            if not abstract or hashlib.sha256(abstract.encode()).hexdigest() != record[side + '_abstract_sha256']:
                raise ValueError('Connection evidence does not match source abstract')
        if not all(isinstance(record.get(k), str) and record[k].strip()
                   for k in ('explanation', 'evidence')):
            raise ValueError('Connection requires explanation and evidence')
        # Symmetric relationships get one key regardless of endpoint order.
        pair = sorted((source, target)) if kind in {'overlaps', 'related_topic'} else [source, target]
        key = 'ai:abstract:' + hashlib.sha256(json.dumps([*pair, kind]).encode()).hexdigest()
        if key in seen:
            raise ValueError('Duplicate connection in batch')
        seen.add(key)
        result.append((key, record))
    return result


def load_connections(conn, connections):
    if not connections:
        return 0
    identifiers = sorted({r[k] for _, r in connections for k in ('from_openalex_id', 'to_openalex_id')})
    stored = {source: (work_id, abstract) for source, work_id, abstract in conn.execute(
        'SELECT openalex_id,work_id,abstract FROM works WHERE openalex_id = ANY(%s)',
        (identifiers,)).fetchall()}
    values = []
    for key, record in connections:
        ids = []
        for side in ('from', 'to'):
            work_id, abstract = stored[record[side + '_openalex_id']]
            if not abstract or hashlib.sha256(abstract.encode()).hexdigest() != record[side + '_abstract_sha256']:
                raise ValueError('Stored abstract differs from connection evidence')
            ids.append(work_id)
        values.append((key, *ids, record['connection_type'], record['explanation'], record['evidence']))
    with conn.cursor() as cur:
        cur.executemany('''INSERT INTO work_connections
            (import_key,from_work_id,to_work_id,connection_type,explanation,evidence,
             review_basis,proposed_by,review_status)
            VALUES (%s,%s,%s,%s,%s,%s,'abstract','ai','suggested')
            ON CONFLICT (import_key) DO NOTHING''', values)
        return cur.rowcount


def initialize_schema(url):
    """Only initialize an empty public schema; never drop or replace existing tables."""
    import psycopg
    with psycopg.connect(url, connect_timeout=10, autocommit=True) as conn:
        existing = conn.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='public' LIMIT 1").fetchone()
        if existing:
            raise ValueError('Schema initialization requires an empty public schema')
        conn.execute((ROOT / 'db/schema.sql').read_text(encoding='utf-8'))
    print('Created five-table schema. Schema setup commits separately from data loading.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path,
                        default=ROOT / 'data/raw/20261029T155716Z_d357540f')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--init-schema', action='store_true', help='Create tables in an empty database only')
    parser.add_argument('--assessments', type=Path, help='Approved private assessment JSON batch')
    parser.add_argument('--connections', type=Path, help='Private abstract-only AI connection suggestions')
    args = parser.parse_args()
    try:
        rows = prepare(args.run_dir)
        assessments = prepare_assessments(args.assessments, rows)
        connections = prepare_connections(args.connections, rows)
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
        if args.init_schema:
            initialize_schema(url)
        with psycopg.connect(url, connect_timeout=10) as conn:
            added = load_rows(conn, rows)
            added['work_assessments'] = load_assessments(conn, assessments)
            added['work_connections'] = load_connections(conn, connections)
            counts = conn.execute('''SELECT
                (SELECT count(*) FROM works), (SELECT count(*) FROM authorships),
                (SELECT count(*) FROM work_assessments), (SELECT count(*) FROM reading_notes),
                (SELECT count(*) FROM work_connections)''').fetchone()
        print('Committed new rows: ' + json.dumps(added))
        print('Table counts: ' + json.dumps(dict(zip(
            ('works','authorships','work_assessments','reading_notes','work_connections'), counts))))
        print('Existing rows and personal notes were not changed.')
        return 0
    except Exception as error:
        # Database/connection exceptions can contain credentials or personal data.
        print('Load failed (' + type(error).__name__ + '). No partial transaction committed.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
