# Part C: run history and status

Implemented November 12, 2026. Migration 006 is installed in the live database.
`sync_state` continues to store discovery progress. `sync_runs` records individual
invocations; existing papers are still never refreshed by ordinary discovery.

## Columns

| Column | Meaning |
|---|---|
| run_id | UUID primary key generated once per invocation |
| started_at / finished_at | Database timestamps; finished_at remains NULL if completion could not be recorded |
| status | CHECK-constrained success, partial, or failed |
| records_fetched | Work records returned across successful API responses, including candidates and repeated hits; not unique additions |
| records_inserted / records_updated | Committed work rows, not authorships; zero on failure or preview |
| error_message | Fixed, safe failure category; never raw exception text, connection strings, or API responses |
| trigger | CHECK-constrained manual or schedule; supplied by --trigger |
| dry_run | Distinguishes previews from live runs |
| mode | discovery_only or targeted_refresh |
| outcome | completed, preview, already_completed_today, unfinished, or rolled_back |
| details | Selected numeric counters; previews include proposed insert/update counts |

Author-credit counters are separate details and do not inflate work-update counts.
On previews, those detail counts are proposals too. Awaiting AI assessment does
not make metadata collection partial: model assessment is a separate future step.

## Status and failure semantics

- **success:** completed the operation, including a clearly identified same-day
  no-op or preview. Neither no-ops nor previews advances reported freshness.
- **partial:** a discovery search completed but found zero eligible new papers
  within its search limits, so it missed the user's minimum-one target. It logs
  zero inserts and exits nonzero. It can retain discovery progress; it is not
  a half-written batch. Same-day no-op runs remain success, not partial.
- **failed:** source/configuration/validation/database failure or interruption.
  The data/progress transaction rolls back; committed change counts are zero.

A failed/unfinished sentinel is committed before source work starts. Success
history, library changes, and progress then commit in one transaction. If anything
fails, the sentinel survives and is finalized separately with a safe error.
During execution, or after a hard kill, status is conservatively failed and
finished_at is NULL: the row has no confirmed outcome. Do not label that as a
completed failure merely because the script is still working. SIGKILL or loss of
database connectivity can prevent final counts/timestamps from being recorded.
The script does not guess when an interrupted process stopped.

If the database cannot be reached initially, no database row can be written;
the process exits nonzero and prints a safe failure with its run ID, plus a local
summary when the output folder is writable. Malformed CLI arguments/help are
not sync runs. The table must exist before the script can log anything.

Errors exclude exception messages entirely. Targeted-maintenance reasons remain
outside sync_runs; only whitelisted counters enter its details. The reader role
has SELECT and a SELECT RLS policy only. Run writes use the owner connection.

## Commands

```powershell
.\.venv\Scripts\python.exe ingest/sync.py --dry-run --trigger manual
.\.venv\Scripts\python.exe scripts/status.py
```

For a real manual run, omit --dry-run. The future GitHub workflow must pass
`--trigger schedule` only for scheduled events, otherwise manual. This field is
caller-supplied provenance; scheduled-run evidence must also come from Actions.
No workflow or schedule is installed by Part C.

`scripts/status.py` uses APP_DATABASE_URL, verifies app_reader, and opens a
read-only transaction. Its SQL is in `db/sync_status.sql`. It reports:

- Last successful **live discovery**, excluding previews and same-day skips.
- Last committed work addition/update separately, so a successful check is not
  confused with a changed article.
- Seven-day counts and the latest 20 runs in that interval, including failures.

Seven-day membership uses started_at. Freshness timestamps search all recorded
history. Historical imports before sync_runs existed are not reconstructed or
claimed as logged syncs. A NULL freshness timestamp is explicit, not fabricated.

## Verification

November 12, 2026: seven PostgreSQL tests used connection-local temporary tables.
They verified success and separate no-op rows, failure rollback with a retained
safe log, dry-run zero committed counts, partial empty search, interruption,
the status CHECK constraint, and exclusion of old runs from seven-day totals.
The original discovery/retry offline tests also passed.

Permission check as app_reader:

```text
SELECT count(*) FROM public."sync_runs";
  SELECT succeeded; rows: 0
DELETE FROM public."sync_runs" WHERE false;
  permission denied (SQLSTATE 42501) [expected]
INSERT INTO public."sync_runs" ("status") SELECT "status" FROM public."sync_runs" WHERE false;
  permission denied (SQLSTATE 42501) [expected]
[ok] All 7 tables readable; INSERT and DELETE denied; no changes committed.
```

Before the live preview, predicted up to five proposed additions, no existing
article updates, and zero committed changes. The preview's audit row is retained;
the library and discovery progress are rolled back. See its actual result below.

Observed preview run `0a968845-91fd-40b3-a16e-880b4a8bd6ed`:
started 2026-11-12 14:14:08.784947 UTC, finished 14:14:18.198337 UTC;
status success, trigger manual, dry_run true, outcome preview.
Two requests fetched 200 candidates. Proposed: 5 works and 16 author credits;
0 work updates. Committed: 0 inserted, 0 updated. The reader status report returned
one preview, zero live successes, zero seven-day committed work changes, and NULL
live discovery/change timestamps. No earlier run evidence was backfilled.
