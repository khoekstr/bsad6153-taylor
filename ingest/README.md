# ingest/

## Part C: run the database load

From the repository folder, using the Session pooler configured in local `.env`:

```powershell
.\.venv\Scripts\python.exe ingest/load.py --dry-run
.\.venv\Scripts\python.exe ingest/load.py
```

For the private assessment batches, use each batch's stable path on reruns:

```powershell
.\.venv\Scripts\python.exe ingest/load.py --assessments C:/BSAD6153/planning/assessments/pilot_10.json
.\.venv\Scripts\python.exe ingest/load.py --assessments C:/BSAD6153/planning/assessments/remaining_assessments.json
```

Only for the FIRST setup of an empty database, add `--init-schema`. It refuses existing
public tables and never drops them. Schema creation commits separately; data loading
uses one transaction so a failure cannot leave half a batch loaded. Do not use
`--init-schema` for the duplicate-check run.

Works load before their author credits; approved assessments load after works. All
record values use query parameters. Unique source IDs, work/author pairs, and assessment
import keys support `ON CONFLICT DO NOTHING`. The command prints new-row and total-row
counts; the second identical run should insert zero rows. It does not generate AI
assessments or populate personal notes. Saved AI connection suggestions can also be
imported using the command below. Private assessment data remains
outside the public course repository. The completed pass contains 481 assessments;
23 works lack usable abstracts. See `docs/assessment_process.md` for coverage,
rating interpretation, and the proposed weekly workflow.

For the completed connection batch:

```powershell
.\.venv\Scripts\python.exe ingest/load.py --connections C:/BSAD6153/planning/assessments/connections.json
```

The existing Supabase database already has the additive connection-key migration.
For another preexisting database, apply `db/migrations/001_connection_import_key.sql`
once before using this option. New databases get the field and unique index from
`db/schema.sql`. Connections remain `suggested` and require no human approval.
Both abstract hashes are checked, and existing connection keys are skipped without
changing status or comments. No model calls occur during loading or reruns.

Code that moves data from your API into your database. You build it with your AI agent, one piece per week:

| Week | File | What it does |
|---|---|---|
| 1 | `fetch.py` | Calls your API: authentication, pagination, rate limits, retries. Saves raw JSON to `data/raw/`. |
| 2 | `load.py` | Turns the raw JSON into rows in your tables, using parameterized queries. Running it twice must not create duplicates. |
| 3 | `sync.py` | Combines fetch and load into one incremental, idempotent sync that GitHub Actions runs on a schedule and records in `sync_runs`. |

Local setup/loading and the later sync use `DATABASE_URL`. Future application access
must use limited roles rather than the owner connection.

## Milestone 2 loading

The five-table design is documented in `docs/schema.md`. `load.py --dry-run` validates
the reviewed selection without a database connection. `load.py` imports works with
`source = 'openalex'`, then author credits. Parameterized inserts skip existing unique
keys. The optional `--assessments` argument imports approved AI assessments after
their parent works; it never invents personal notes or connections. Categories are controlled
text lists on assessments; there are no category tables to seed. Search groups stay
in the selection manifest, not the works table or category selections.

The loader uses `reviewed_selection.json` in the selected run folder; downloaded author
profiles are retained as raw evidence, while credits come from each work's authorships.
Author order follows the source array. Apply `db/schema.sql` only to a new database;
it is not a migration from the prior draft. Live row counts and duplicate-free reruns
were verified November 7, 2026; see `docs/load_verification.md`.

## Part B: OpenAlex retrieval

Run from the project folder after reviewing the script. The existing virtual environment
needs the packages in requirements.txt. Put OPENALEX_API_KEY in local .env; never in code
or command arguments. Authentication uses a bearer header, not a URL parameter.

```powershell
.\.venv\Scripts\python.exe -m unittest ingest.test_fetch -v
.\.venv\Scripts\python.exe ingest/fetch.py --write-sample
```

The first command is offline. The second makes live API requests and writes files.
It does not load a database, call an LLM, purchase credits, or change account settings.
Remain on the free OpenAlex account without prepaid credits for $0 out-of-pocket usage.
The 150-request cap is a runaway-request safeguard, not a provider billing cap.

### Selection and interpretation

selection.json holds the six topic groups and 12 requested paper titles. Reviewed
required_ids take precedence over title searches, so abbreviated titles and multiple
versions resolve to the intended OpenAlex work. Exact normalized
title matching is deliberately conservative: shortened or ambiguous titles are reported
for manual matching, never silently substituted. The two personal essays are listed as
future manual additions, not counted toward the API requirement. Required matches count
toward 500, so category targets are approximate. Category order can affect the final mix.

General searches select English open-access articles with no page-length or date cutoff.
Queries alternate within each group using the API's default search ordering. These are
candidates, not a quality ranking, confirmed reading history, or a verified historical
canon. The proposed 350-recent/150-older split is not enforced in this first version.
Review the actual results before deciding whether to refine the queries/date mix.

### Retrieval and failure behavior

- Cursor paging starts at `*`, then follows `meta.next_cursor`, with repeated-cursor guards.
- Unique OpenAlex work IDs determine the count; duplicate and invalid records are counted.
- Separate author records are requested in batches using the selected works' author IDs.
- Requests wait two seconds apart; timeouts, connection errors, malformed JSON, 429,
  and 5xx responses receive at most five attempts with exponential backoff.
- Retry-After is respected. Waits longer than 60 seconds or an exhausted daily allowance
  stop the run for later review instead of waiting indefinitely.
- Missing optional fields are counted; missing work ID/title causes a skip. No fabricated values.
- A shortfall, no related authors, or a fatal request error produces exit code 1.
  Unresolved named articles remain explicit warnings even if the 500-record count succeeds.

Each run creates a new ignored `data/raw/<UTC time>_<run id>/` folder containing raw
successful JSON responses, selection settings, fetch.log, and summary.json. Raw responses
may include more candidates than selected; summary.selected lists the actual IDs and files.
Do not treat all downloaded records as recommendations. Error bodies and request headers
are never logged. Optional missing-field counts appear in the summary.

`--write-sample` creates `data/sample/openalex_sample.json` only after a successful run.
It contains one unchanged work and one unchanged author, labeled as excerpts. Review it
before committing; the script does not commit or push anything. No real sample has been
created until that live command succeeds.

Check summary.json for unique_works >= 500, unique_authors > 0, complete: true,
unresolved required titles, and missing-field counts. A fresh rerun preserves earlier runs.
For Part B evidence, show the summary, a raw response, the paging/retry code, and the sample.

Official documentation checked October 29, 2026:
- https://help.openalex.org/api/authentication/
- https://help.openalex.org/api/paging/
- https://help.openalex.org/api/filtering/
- https://help.openalex.org/access/pricing/

The student confirmed completing the documentation review in chat. Record personal
verification details in the course AI review log in your own words.
