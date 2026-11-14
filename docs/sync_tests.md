# Part G: sync safety tests and golden-reference comparison

Executed November 14, 2026. Three controlled scenarios passed. The required
comparison after two additional scheduled syncs is **pending**; today's immediate
golden-reference recheck is not a substitute.

## Scope and reproduction

`evals/run_sync_tests.py` invokes production `synchronize`, `refresh_one`, and
`run_logged` with synthetic source responses and real PostgreSQL transactions.
Only connection-local TEMP copies of works, authorships, sync_state, and sync_runs
are written. Each table is verified to resolve to pg_temp; the harness uses a
separate advisory lock so it does not compete with the scheduled pipeline.
No HTTP requests, live manual syncs, or GitHub dispatches occur. No live paper,
note, assessment, or production audit row is changed. The owner connection is
used to create temporary tables; golden-reference checks use app_reader.

The seven captured test sync_runs rows below are **temporary-table evidence**,
not scheduled-run evidence. Temporary tables disappear on connection close.

```powershell
python evals/run_sync_tests.py --output data/evals/sync_scenarios_2026-11-16.json
```

Use a new evidence filename for each execution. Predictions are printed before
the scenarios run. Synthetic IDs are never inserted into public tables.

## 1. Back-to-back rerun

**Prediction:** First run inserts one and updates zero. Immediate rerun fetches,
inserts, and updates zero; one paper and two author credits remain.

**Action:** Start with empty temporary tables, perform discovery, and immediately
repeat within the same UTC day. The second fake source has no responses, making
an unexpected fetch fail the test.

**Observed:** Both runs succeeded. The second reported `already_completed_today`,
with zero fetched/inserted/updated. Counts before and after the rerun were
identical: one paper, two author credits, one progress row, no duplicate OpenAlex
IDs. This exercises the daily gate; it does not by itself test source deduplication.

## 2. Interrupted write and recovery

**Prediction:** An interruption after writes rolls them back while retaining a
failed audit row. Recovery inserts exactly one paper without duplicates.

**Action:** Inject `KeyboardInterrupt` immediately after the real upsert wrote a
paper and its two author credits, before the data transaction committed. Rerun
discovery with the same synthetic input. This is a catchable interruption,
not an operating-system hard kill.

**Observed:** The in-transaction check saw one paper and two credits. After the
interruption, all paper, credit, and progress counts were zero. The audit row
survived with `failed / rolled_back`, a completion time, and zero committed
changes. Recovery inserted one paper and two credits with one progress row and
no duplicates. No half-written data survived.

## 3. Simulated source change

**Prediction:** Seed inserts one paper. A targeted refresh changes incoming
citations from 2 to 12 and the title, inserting zero and updating one. Repeating
the identical refresh updates zero; discovery progress remains unchanged.

**Action:** Seed `Part G source title`, citation count 2. Explicitly refresh that
synthetic work with title `Part G corrected source title`, citation count 12.
Repeat the refresh with identical metadata.

**Observed:** The first refresh updated one paper; stored title and generated
citation count reflected the new source. The second inserted/updated zero.
One paper and two credits remained, with no duplicate IDs. Discovery progress
was unchanged; the additional targeted-refresh progress row was expected.
Ordinary discovery intentionally does not refresh existing papers: this tests
the supported explicit maintenance path.

**Test development finding:** The first source-change rehearsal failed because
the harness incorrectly attached the works timestamp trigger to temporary
sync_state, which lacks first_seen_at. Removing that test-only trigger corrected
the harness. All three scenarios then passed. No production sync fix was needed.

## Actual scheduled runs, separate from simulations

Both recorded scheduled runs occurred before the Part F baseline:

| GitHub run | Database run ID | Database start (Central) | Outcome | Fetched / inserted / updated |
|---|---|---|---|---|
| [43536127990](https://github.com/khoekstr/bsad6153-taylor/actions/runs/43536127990) | `4c9a8077-ac77-478d-9d19-081a4eb228f1` | Nov 13, 18:44:14 | success / completed | 200 / 5 / 0 |
| [43629471106](https://github.com/khoekstr/bsad6153-taylor/actions/runs/43629471106) | `acb8ee68-8274-43db-a11e-219f814c5c25` | Nov 14, 12:58:11 | success / already_completed_today | 0 / 0 / 0 |

The first was November 14 in UTC, so it consumed that UTC day's allowance. The
second independently demonstrates the daily gate in live scheduled operation;
it is not a back-to-back test or a post-baseline run.

## Golden-question comparison

Baseline: `data/evals/reference_baseline.json`, November 14 at 14:01:49 Central.
Today's follow-up: `data/evals/reference_2026-11-14_part_g.json` (exact time below).
Both used app_reader and read-only, consistent snapshots. All 12 queries passed.

**Changed answers: none. Unchanged: Q01–Q12.** Q13–Q15 are decline cases and were
not executed; this is not a chatbot refusal evaluation. The comparison checks
actual returned columns/values, not just row counts. It requires matching CSV and
per-query hashes; snapshot timestamps alone do not count as changed answers.

At the scheduled-history check there were **zero scheduled runs after the
baseline**, so unchanged answers were expected. Q11 still reported 30 pending
assessments and Q12 still identified the November 13 addition-producing run.
Relevance/category results can stay unchanged until incoming papers are assessed;
citation rankings can remain unchanged because discovery does not refresh old
counts. Moving calendar windows can also change answers independently of sync.

The full answer snapshots contain private notes and are ignored by Git. Only
the queries, checker, harness, and this evidence summary are committed.

```powershell
python evals/check_reference.py --compare data/evals/reference_baseline.json --output data/evals/reference_2026-11-16.json
```

## Monday completion gate

1. Verify at least two more scheduled syncs after **2026-11-14 14:01:49 Central**
   using Actions event provenance and database audit rows. Distinguish additions
   from successful no-ops. If fewer than two occurred, leave this requirement pending.
2. Run the command above, preserving the original baseline and unchanged queries.
3. Record changed IDs and causes: new papers, new assessments, or date-window
   changes. Investigate unexpectedly unchanged ingestion-sensitive answers.
4. Confirm every SQL query still passes. Document the results here, separately
   from future chatbot refusal evaluation.

**Status:** Three controlled safety scenarios and today's golden recheck passed.
The required post-two-scheduled-sync comparison is **not yet complete**.

## Captured temporary sync_runs evidence

All rows below have `trigger=manual` and `dry_run=false`, describing synthetic
test invocations only. Error text and counters are captured from the actual
temporary sync_runs rows. These rows were not inserted into production history.

Immediate golden recheck time: **2026-11-14T14:08:08.385266-06:00**.

### rerun

| Run ID | Started / finished (UTC) | Status / outcome | Fetched / inserted / updated |
|---|---|---|---|
| `abd65890-e3a0-4bb2-873b-21b9af4469b3` | 2026-11-14T20:07:54.941354+00:00 / 2026-11-14T20:07:56.151155+00:00 | success / completed | 2 / 1 / 0 |
| `97c86759-d3e0-4c64-8b0a-6000067b71a6` | 2026-11-14T20:07:56.380806+00:00 / 2026-11-14T20:07:56.98134+00:00 | success / already_completed_today | 0 / 0 / 0 |

- `abd65890-e3a0-4bb2-873b-21b9af4469b3`: mode `discovery_only`; error_message `None`; details `{"abstracts_changed": 0, "assessment_pending": 1, "authorships_inserted": 2, "authorships_removed": 0, "authorships_updated": 0, "requests": 2}`.
- `97c86759-d3e0-4c64-8b0a-6000067b71a6`: mode `discovery_only`; error_message `None`; details `{}`.

### interrupted_run

| Run ID | Started / finished (UTC) | Status / outcome | Fetched / inserted / updated |
|---|---|---|---|
| `f61b7747-2829-4e94-ac56-3e629f90942a` | 2026-11-14T20:07:58.820966+00:00 / 2026-11-14T20:08:00.171249+00:00 | failed / rolled_back | 2 / 0 / 0 |
| `306e1c4f-4518-43c2-b4f1-2f5a19c7d404` | 2026-11-14T20:08:00.395609+00:00 / 2026-11-14T20:08:01.595802+00:00 | success / completed | 2 / 1 / 0 |

- `f61b7747-2829-4e94-ac56-3e629f90942a`: mode `discovery_only`; error_message `Run interrupted; data and progress transaction rolled back.`; details `{}`.
- `306e1c4f-4518-43c2-b4f1-2f5a19c7d404`: mode `discovery_only`; error_message `None`; details `{"abstracts_changed": 0, "assessment_pending": 1, "authorships_inserted": 2, "authorships_removed": 0, "authorships_updated": 0, "requests": 2}`.

### source_change

| Run ID | Started / finished (UTC) | Status / outcome | Fetched / inserted / updated |
|---|---|---|---|
| `6d7694e8-100b-42ba-8998-41ca43d9ffad` | 2026-11-14T20:08:03.460991+00:00 / 2026-11-14T20:08:04.615629+00:00 | success / completed | 2 / 1 / 0 |
| `e7077740-e5d8-4398-9c7d-1ecb6203136a` | 2026-11-14T20:08:04.860815+00:00 / 2026-11-14T20:08:05.901359+00:00 | success / completed | 2 / 0 / 1 |
| `9526463a-d3f1-49d7-83e7-214ff638d1c5` | 2026-11-14T20:08:06.060726+00:00 / 2026-11-14T20:08:07.081441+00:00 | success / completed | 2 / 0 / 0 |

- `6d7694e8-100b-42ba-8998-41ca43d9ffad`: mode `discovery_only`; error_message `None`; details `{"abstracts_changed": 0, "assessment_pending": 1, "authorships_inserted": 2, "authorships_removed": 0, "authorships_updated": 0, "requests": 2}`.
- `e7077740-e5d8-4398-9c7d-1ecb6203136a`: mode `targeted_refresh`; error_message `None`; details `{"abstracts_changed": 0, "authorships_inserted": 0, "authorships_removed": 0, "authorships_updated": 0, "requests": 2}`.
- `9526463a-d3f1-49d7-83e7-214ff638d1c5`: mode `targeted_refresh`; error_message `None`; details `{"abstracts_changed": 0, "authorships_inserted": 0, "authorships_removed": 0, "authorships_updated": 0, "requests": 2}`.
