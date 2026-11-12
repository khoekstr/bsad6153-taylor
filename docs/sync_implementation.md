# Part B: bounded, transactional sync

Implemented November 11, 2026; revised to discovery-only at the user's direction. Entry point: `ingest/sync.py`.

## Run

Use existing local DATABASE_URL (owner Session pooler) and OPENALEX_API_KEY.
Migration `db/migrations/005_sync_state.sql` is applied to the current database;
for another existing database apply migrations 005 and 006 and rerun `db/roles.sql` first. New empty
databases get sync_state from schema.sql, then grants from roles.sql.

```powershell
.\.venv\Scripts\python.exe ingest/sync.py --dry-run
.\.venv\Scripts\python.exe ingest/sync.py
```

Dry-run fetches real responses and exercises real upserts but rolls back all work
and progress. Identity sequences can still advance, leaving harmless ID gaps.
The second command commits. Neither command schedules future runs or invokes AI.
The initial 500-record fetch/load commands remain available unchanged in purpose.

## Discovery only; existing articles are left alone

The normal command searches for new papers and adds at most five per UTC day.
It never requests a batch of existing IDs, compares their metadata, refreshes
abstracts, or rewrites their authorships. Existing search hits are skipped by ID
before validation. Local IDs, DOI values, and titles are read only to avoid
adding duplicates. The insertion path uses ON CONFLICT DO NOTHING as an extra
guard against changing a record another importer inserted concurrently.

The database's `sync_state` row holds the last successful discovery start time,
completed UTC day, discovery cursors, preference hash, added IDs and latest counts.
These are progress markers; Part C now separately records per-run history in
[sync_runs](sync_runs.md).
Old refresh-cursor fields, if present, are ignored; no rotating refresh is used.

OpenAlex restricts source-created/updated-date filters to paid sync plans.
Free discovery examines recent results and resumes older candidate pages, so
older publications remain eligible without claiming complete newly-indexed
coverage. Optional paid mode uses an inclusive source-update filter to discover
new-to-library candidates; it still skips every existing ID. The any-category
fallback may search all dates. Only chosen new papers are ingested; this is a
curated selection, not an exhaustive mirror of OpenAlex.

## Rare, explicit maintenance

Refreshing an existing article requires both its exact OpenAlex ID and a reason:

```powershell
python ingest/sync.py --refresh-id https://openalex.org/W123 --reason "Check a reported source correction" --dry-run
```

W123 above is a placeholder: use an actual existing ID. This command fetches only
that one article. Omit --dry-run only when deliberately applying that correction.
There is no automatic refresh triggered by viewing/using an article. Missing IDs
or missing reasons fail before API requests. Missing source responses leave the
stored article untouched. The reason is saved in a separate refresh:<ID> state
row and local summary; it is not sent to OpenAlex. Maintenance does not consume
or advance the daily discovery allowance/watermark.

The upsert path remains available for this explicitly requested maintenance and
Part B's source-change demonstration. Daily runs intentionally do not propagate
changes to old records; this is the user's chosen departure from continuously
mirroring source updates and should be described in the assignment submission.

Sources checked November 11, 2026:
- [OpenAlex filtering](https://help.openalex.org/api/filtering/)
- [Cursor paging](https://help.openalex.org/api/paging/)
- [Sorting](https://help.openalex.org/api/sorting/)

## Data ownership and transactions

New OpenAlex candidates -> shared `load.prepare_record` validation -> works insert
by openalex_id -> author-credit inserts -> sync_state. Explicit maintenance alone
uses works upserts and author-credit reconciliation.
Abstract word positions become text. Incomplete author credits are omitted with
a warning and retained in raw metadata. Author ordering is source order.

For explicit maintenance, `ON CONFLICT ... DO UPDATE ... WHERE ... IS DISTINCT FROM` avoids firing update
triggers on identical values. Comparison includes source fields and raw metadata,
except transport-only updated_date and search relevance_score. The old raw
updated_date remains if that is the only difference. Real changes stamp
last_updated_at; the existing trigger preserves first_seen_at.

During explicit maintenance only, changed author positions are temporarily
cleared to avoid unique-order conflicts and obsolete source credits are removed.
Notes, user ratings, uploads, AI assessments, and connections are preserved.
Changed abstracts are listed in the targeted maintenance result for reassessment;
no AI assessment is automatically regenerated or represented as current.

One transaction covers all source writes and progress advancement; an advisory
transaction lock rejects concurrent syncs. Any fetch, validation, or DB failure
rolls back the run. Retrying starts from the last committed state. Network calls
are bounded by timeouts, five attempts, request cap, exponential backoff, and
Retry-After; requested waits over 60 seconds or exhausted allowance fail cleanly.
Exit status is nonzero on failure. Errors do not print credentials/response bodies.
Ignored `data/raw/sync_*/` retains downloaded responses and local run summaries.

## Historical preview, before the discovery-only correction

The superseded rotating-refresh preview (no longer the default) recorded: predicted 5 inserted and 0-100 updated existing works;
the precise update count was unknown until current metadata was compared.
Observed: 5 proposed inserts, 99 updates, 4 changed abstracts, 15 author-credit
inserts, 1 author-credit update, 0 removed credits, 0 missing source works.
Three requests fetched 300 candidate/refresh records. All writes rolled back.
The large update count includes changes in raw metadata, not just paper titles.
The user rejected routine metadata review after this preview. None of those 99
updates was committed. Existing articles now remain untouched during daily runs.

Offline tests and connection-local temporary-table PostgreSQL tests cover:
five-addition limit, hard filters, duplicates, priority/paused topics, fallback,
cursor reuse, insertion, unchanged replay including timestamps,
source changes, author swaps, rollback, dry run, and same-day no-op rerun.
The existing fetch tests exercise 429/5xx/network retries and bounded failure.

Predictions for fixture DB tests: first insert = 1/0; identical replay = 0/0;
changed source = 0/1; invalid second record = 0 committed parents/children;
same-day sync rerun = 0 API calls and 0/0. All were observed.
These Part B tests are not evidence of scheduled runs. Part C subsequently added
run history; see its separate evidence in sync_runs.md.

New table grant verified as app_reader: SELECT sync_state succeeded (0 rows);
INSERT and DELETE both returned permission denied (SQLSTATE 42501).

## Verification of the revised policy

Regression tests supply an existing paper with changed and malformed source
metadata alongside a new paper. Expected: one insert, zero updates, identical
stored old record/authorships/timestamps, and no API request by existing ID.
A separate test checks that deliberate maintenance requires a reason and an
existing ID, requests only that ID, and leaves discovery progress untouched.
No live source refresh or library mutation is needed for these tests.
