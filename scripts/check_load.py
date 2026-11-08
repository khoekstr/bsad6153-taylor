"""Verify source data and save/compare a private fingerprint across loader reruns."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ingest.load import prepare, prepare_assessments, prepare_connections


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assessments', type=Path)
    parser.add_argument('--connections', type=Path)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--compare', action='store_true')
    args = parser.parse_args()
    try:
        import psycopg
        from dotenv import load_dotenv
        load_dotenv(ROOT / '.env')
        rows = prepare(ROOT / 'data/raw/20261029T155716Z_d357540f')
        assessments = prepare_assessments(args.assessments, rows)
        connections = prepare_connections(args.connections, rows)
        with psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=10) as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            works = conn.execute('''SELECT openalex_id,title,doi,publication_date,
                publication_year,work_type,language,abstract,openalex_topic,is_open_access,
                pdf_url,source_url FROM works WHERE source='openalex' ORDER BY openalex_id''').fetchall()
            assert works == sorted([tuple(v) for v, _, _ in rows]), 'Work/source mismatch'
            credits = conn.execute('''SELECT w.openalex_id,a.author_openalex_id,a.author_name,a.author_order
                FROM authorships a JOIN works w USING(work_id)
                WHERE w.source='openalex' ORDER BY 1,2''').fetchall()
            expected = sorted((v[0], *credit) for v, _, cs in rows for credit in cs)
            assert credits == expected, 'Author/source mismatch'
            for key, source_id, _, assessment in assessments:
                found = conn.execute('''SELECT to_jsonb(a),w.openalex_id FROM work_assessments a
                    JOIN works w USING(work_id) WHERE a.import_key=%s''', (key,)).fetchone()
                assert found and found[1] == source_id, 'Missing/wrong assessment parent'
                assert all(found[0][k] == value for k, value in assessment.items()), 'Assessment mismatch'
            if connections:
                actual = {key: (record, source, target) for key, record, source, target in conn.execute('''
                    SELECT c.import_key,to_jsonb(c),f.openalex_id,t.openalex_id
                    FROM work_connections c JOIN works f ON f.work_id=c.from_work_id
                    JOIN works t ON t.work_id=c.to_work_id WHERE c.import_key = ANY(%s)
                    ''', ([key for key, _ in connections],)).fetchall()}
                assert len(actual) == len(connections), 'Missing connections'
                for key, expected in connections:
                    record, source, target = actual[key]
                    assert (source, target) == (expected['from_openalex_id'], expected['to_openalex_id']), 'Wrong connection parents'
                    assert all(record[k] == expected[k] for k in (
                        'connection_type','explanation','evidence','review_basis','proposed_by','review_status')), 'Connection mismatch'
                    assert record['user_comment'] is None, 'Unexpected personal comment'
            tables = conn.execute("SELECT relname,relrowsecurity FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind='r' ORDER BY relname").fetchall()
            assert len(tables) == 5 and all(t[1] for t in tables), 'Expected RLS on five tables'
            # Fixed queries: fingerprint all rows, including IDs and audit timestamps.
            snapshots = {
                'works': conn.execute('SELECT to_jsonb(w) FROM works w ORDER BY work_id').fetchall(),
                'authorships': conn.execute('SELECT to_jsonb(a) FROM authorships a ORDER BY authorship_id').fetchall(),
                'work_assessments': conn.execute('SELECT to_jsonb(a) FROM work_assessments a ORDER BY assessment_id').fetchall(),
                'reading_notes': conn.execute('SELECT to_jsonb(n) FROM reading_notes n ORDER BY note_id').fetchall(),
                'work_connections': conn.execute('SELECT to_jsonb(c) FROM work_connections c ORDER BY connection_id').fetchall(),
            }
        counts = {k: len(v) for k, v in snapshots.items()}
        digest = hashlib.sha256(json.dumps(snapshots, sort_keys=True, default=str).encode()).hexdigest()
        evidence = {'counts': counts, 'sha256': digest}
        if args.compare:
            assert json.loads(args.snapshot.read_text()) == evidence, 'Rerun changed stored records'
        else:
            args.snapshot.parent.mkdir(parents=True, exist_ok=True)
            args.snapshot.write_text(json.dumps(evidence, indent=2)+'\n')
        print('Verified source fields, author credits, supplied assessments/connections, and RLS.')
        print(json.dumps(counts))
        print('All stored rows and audit timestamps unchanged.' if args.compare else 'Saved private rerun fingerprint.')
        return 0
    except Exception as error:
        print('Verification failed (' + type(error).__name__ + '). Details suppressed to protect private data.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
