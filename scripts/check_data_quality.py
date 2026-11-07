"""Measure reviewed local OpenAlex data without database access or network calls."""
import argparse
from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ingest.load import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, default=ROOT / 'data/raw/20261029T155716Z_d357540f')
    parser.add_argument('--as-of', type=date.fromisoformat, default=date(2026, 11, 7))
    parser.add_argument('--output', type=Path, help='Optional path for the measured JSON evidence')
    args = parser.parse_args()
    rows = prepare(args.run_dir)  # Reuse the actual loader's validation and transformations.
    manifest = json.loads((args.run_dir / 'reviewed_selection.json').read_text(encoding='utf-8-sig'))
    missing = Counter()
    groups = defaultdict(lambda: Counter(works=0, missing_abstracts=0))
    distributions = {key: Counter() for key in ('language', 'type', 'open_access', 'year')}
    dois, titles = defaultdict(list), defaultdict(list)
    examples = defaultdict(list)
    future_dates, date_year_mismatches = [], []
    for values, raw, credits in rows:
        work_id = values[0]
        fields = {'abstract': values[7], 'publication_date': values[3], 'doi': values[2],
                  'language': values[6], 'primary_topic': values[8], 'pdf_url': values[11],
                  'authorships': credits}
        for field, value in fields.items():
            if value is None or value == '' or value == []:
                missing[field] += 1
                examples[field].append(work_id)
        group = values[9] or 'unknown'
        groups[group]['works'] += 1
        groups[group]['missing_abstracts'] += values[7] is None
        for key, value in [('language', values[6]), ('type', values[5]),
                           ('open_access', values[10]), ('year', values[4])]:
            distributions[key][str(value)] += 1
        if values[2]:
            doi = values[2].strip().lower().removeprefix('https://doi.org/').removeprefix('http://doi.org/')
            dois[doi].append(work_id)
        titles[' '.join(values[1].casefold().split())].append(work_id)
        if values[3] and values[3] > args.as_of:
            future_dates.append(work_id)
        if values[3] and values[4] and values[3].year != values[4]:
            date_year_mismatches.append(work_id)
    ids = [row[0][0] for row in rows]
    result = {
        'as_of': args.as_of.isoformat(), 'source_run': manifest['source_run'],
        'scope': 'Reviewed local snapshot; not a live database or full-text audit',
        'works': len(rows), 'unique_work_ids': len(set(ids)),
        'duplicate_work_ids': len(ids) - len(set(ids)),
        'authorship_credits': sum(len(row[2]) for row in rows),
        'works_without_raw_authorships': sum(not row[1].get('authorships') for row in rows),
        'raw_authorship_entries': sum(len(row[1].get('authorships') or []) for row in rows),
        'incomplete_raw_author_credits': sum(
            not credit.get('author', {}).get('id') or not (credit.get('author', {}).get('display_name') or '').strip()
            for row in rows for credit in (row[1].get('authorships') or [])),
        'distinct_credited_author_ids': len({credit[0] for row in rows for credit in row[2]}),
        'required_works': len(manifest['required']),
        'missing_required_ids': sorted(set(manifest['required'].values()) - set(ids)),
        'missing': {field: missing[field] for field in fields},
        'missing_examples': {field: ids[:3] for field, ids in examples.items()},
        'selection_groups': dict(sorted(groups.items())),
        'distributions': distributions,
        'duplicate_doi_groups': {key: ids for key, ids in dois.items() if len(ids) > 1},
        'duplicate_normalized_title_groups': {key: ids for key, ids in titles.items() if len(ids) > 1},
        'future_publication_dates': future_dates,
        'date_year_mismatches': date_year_mismatches,
        'loader_validation': 'passed'
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + '\n', encoding='utf-8')
    print(rendered)


if __name__ == '__main__':
    main()
