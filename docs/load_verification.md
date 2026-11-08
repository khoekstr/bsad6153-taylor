# Part C: live load verification

Verified November 7, 2026 against the configured Supabase Session pooler.
The public schema was empty before setup. Five tables were created from `db/schema.sql`.

| Table | Initial run inserted | Initial rerun inserted | Initial count |
|---|---:|---:|---:|
| works | 504 | 0 | 504 |
| authorships | 1,516 | 0 | 1,516 |
| work_assessments | 10 | 0 | 10 |
| reading_notes | 0 | 0 | 0 |
| work_connections | 0 | 0 | 0 |

The initial ten assessments are the user-approved abstract-only chat pilot.
The completion batch subsequently added 471 assessments, bringing the total to
481. No external AI API calls were made. Personal notes and connections were
empty at that stage. A later authorized connection pass is recorded below. See `assessment_process.md`
for scope and the 23 records without usable abstracts.

## How the loader meets the requirements

- Uses the reviewed Milestone 1 manifest to select 504 works from the raw JSON.
- Inserts parent works before child author credits and assessments.
- Uses bound `%s` parameters for all record values, including batched inserts.
- Uses `ON CONFLICT DO NOTHING` on unique source IDs, work/author pairs, and assessment
  import keys. The latter allows deliberate new assessment batches without duplicating
  the same imported pilot.
- Loads data within one transaction. Initial schema creation is a separate transaction.
- Verifies approved assessment abstract hashes against both source and stored abstracts.

## Live evidence

The first run printed:

```text
Committed new rows: {"works": 504, "authorships": 1516, "work_assessments": 10}
```

The second run printed:

```text
Committed new rows: {"works": 0, "authorships": 0, "work_assessments": 0}
```

`scripts/check_load.py` verified the stored source fields, author credits, and every
approved assessment field against their input records. A before/after SHA-256
fingerprint of all stored rows (including IDs, raw JSON, and audit timestamps) was
identical. It also confirmed row-level security is enabled on all five tables; this
does not constitute a full application permission test.

The initial run used individual inserts; the final loader batches the same
parameterized inserts for faster execution. Its live rerun inserted zero rows and
passed the identical-data check. Identity sequences may advance on conflicting
inserts; gaps in IDs are normal and are not duplicate records.

## Reproduce for the screencast

From the project folder, run:

```powershell
.\.venv\Scripts\python.exe ingest/load.py --assessments C:/BSAD6153/planning/assessments/pilot_10.json
.\.venv\Scripts\python.exe ingest/load.py --assessments C:/BSAD6153/planning/assessments/remaining_assessments.json
```

Do not add `--init-schema`: the tables already exist. The private assessment batch
and comparison fingerprint are outside the course repository. The ordinary
`python ingest/load.py` also reruns the source load safely but does not import an
assessment batch unless supplied explicitly.

Incomplete author credits were skipped with a warning and retained in raw JSON.
There are 21 works without usable credits, 16 without any abstract, and 2 without
publication dates. The student still needs to review the implementation and record
the screencast; this report records agent-executed checks, not student review actions.
Seven additional abstract fields were unusable for assessment: five were only
titles, citations, or status text; two contained article bodies. These source
records remain intact.

## Completed assessment pass — November 7, 2026

The completion batch imported 471 new abstract-only AI assessments after the
10-record pilot. The user authorized the batch using the pilot criteria; this
does not imply individual human review of the additional outputs.

```text
Committed new rows: {"works": 0, "authorships": 0, "work_assessments": 471}
Table counts: {"works": 504, "authorships": 1516, "work_assessments": 481, "reading_notes": 0, "work_connections": 0}
```

The same completion batch was then imported again:

```text
Committed new rows: {"works": 0, "authorships": 0, "work_assessments": 0}
```

`scripts/check_load.py` compared every completion assessment field with its saved
input and verified source fields, author credits, and RLS. It saved a private
fingerprint before the rerun. A subsequent check validated the original pilot
and compared the fingerprint across all five tables: all rows, IDs, raw payloads,
and audit timestamps were unchanged. The completion records were also checked
for valid value ratings, abstract-only review basis, and null personal controls,
novelty ratings, and reading-time estimates. Together, the 481 assessed works
and the 23 recorded exceptions cover all 504 selected works.

The final personal-relevance rating distribution is 5 at 1/5, 80 at 2/5, 188 at
3/5, 162 at 4/5, and 46 at 5/5. These are AI judgments, not student evaluations
or measures of paper quality.

## Completed initial connection pass — November 7, 2026

Added 60 abstract-only AI suggestions across 61 works, covering all 46 value-5
works. `suggested` is an attribution/status label, not an approval gate. See
`connections.md` for relationship counts, evidence limits, and reproduction.

An additive migration introduced the nullable unique connection import key without
replacing existing tables. The first connection load inserted 60 rows and zero
works, author credits, or assessments. The second inserted zero rows everywhere.
`scripts/check_load.py --connections ...` verified both parent identities and every
imported field. A before/after fingerprint of all five tables, including audit
timestamps, was identical across the rerun. Final counts are 504 works, 1,516 author
credits, 481 assessments, zero reading notes, and 60 connections.

## Authorized personal-note recovery — November 8, 2026

Recovered six verbatim user remarks for four identified articles from the user's
research chat and an earlier saved retrieval of that same chat. At the user's
explicit request, each note and each work's current user assessment records
`abstract_only`. Reading dates remain unknown; original message timestamps and
source message identities are kept in a private archive. No personal ratings,
favorites, or AI-authored paraphrases were substituted for the user's words.

Two missing articles were added as manual reference-file imports with verified
bibliographic links, adding four author credits. They use `source='upload'` and
point to the private reference JSON, not to a downloaded full-text PDF. Existing
OpenAlex source records, 481 AI assessments, and 60 connections were unchanged.

The additive migration `002_reading_note_import_key.sql` provides a unique original
message key. Verification checked all six note texts and four user statuses. A
second import added zero rows and left all rows and timestamps identical.

Current totals: 506 works (504 OpenAlex, two manual references), 1,520 author
credits, 485 assessment rows (481 AI and four user status rows), six reading notes,
and 60 connections. The OpenAlex verification compares only OpenAlex works and
credits against the ingestion manifest, allowing independent manual references.

Private recovery files live in `C:/BSAD6153/planning/reading_notes/`. The latest
fingerprint is `after_notes_snapshot.json`; earlier fingerprints intentionally
describe earlier database states and should not be overwritten. Personal text
and import scripts are outside the public repository. This recovery covers the
original remarks actually retrieved, not all earlier reading history.

## Course cases — November 8, 2026

Imported all 64 listed references as 63 distinct works across 42 cases; the NBER
and Atlanta Fed links to the same paper share one work. Added 63 AI assessments
based on supplied course excerpts and 80 suggested source connections representing
32 case comparisons, including every weekly success/failure pair. See
[course-case provenance and workflow](course_cases.md).

The first import added 63 works, 63 assessments, and 80 connections. The second
added zero of each and left every row and audit timestamp identical. Both runs
produced fingerprint
`c41087981286667cdc2cf1cfb43501c6fc196974c384ab5c293f62d99811ccb8`.
Verification compared saved assessment and connection fields, checked all 63
works have excerpt-based AI assessments, and preserved all prior records.
The existing load checker also passed source-field, author-credit, supplied
original assessment/connection, and row-level-security checks. Its known warning
about an incomplete original author credit remains unchanged.

Current totals: 569 works, 1,520 author credits, 548 assessments (544 AI and four
user status rows), six reading notes, and 140 connections. Private snapshots,
repeatable import, and readable report are in
`C:/BSAD6153/planning/case_library/`. No personal reading activity was inferred.

## Initial reading-list notes — November 8, 2026

Matched all nine pasted article references to existing works by DOI. Recovered
seven verbatim personal notes for items 1–7 and added seven user reading-status
rows as abstract-only, following the user's earlier explicit instruction. No
reading dates, numeric personal ratings, favorites, or notes for items 8–9 were
invented. Eight works already had AI assessments. Item 8, *The global landscape
of AI ethics guidelines*, received an excerpt-based assessment using the supplied
reading-list summary, with its limited evidence basis documented.

The first import added zero works, seven notes, seven user status rows, and one
AI assessment. Existing records and audit timestamps were preserved. The second
import added zero rows and produced the identical five-table fingerprint:
`9344cc2c50640727261aa5c3f5d170c483f40940f553f37ab038f5c0ea3f3856`.
All nine works have AI assessments; the seven stored notes match the source text.

Current totals: 569 works, 1,520 author credits, 556 assessments (545 AI and 11
user status rows), 13 personal notes, and 140 connections. The private source
archive, note provenance, matched identifiers, repeatable import, readable notes,
and verification snapshots are in
`C:/BSAD6153/planning/reading_notes/first_nine/`.

## Case-brief notes and initial queries — November 8, 2026

Saved the user's DBS brief to both DBS sources and Ford brief to both Ford
sources, adding four notes. Wording was preserved with whitespace normalized.
Added the requested Ableneo pilot article as an undated manual reference, one
excerpt-based AI assessment, and the user's associated note. The retrieved web
excerpt appears incomplete at its final section, so no full-text review is
claimed. Consultancy guidance and unnamed examples are not independent research.
No reading status, reading date, personal rating, or author byline was invented.

Both imports were rerun and added zero rows; existing rows and audit timestamps
were identical. Final fingerprint:
`8dd2d9890298748986aaa13e1668cfbdea30c48f075c843da4a776efafa18fe0`.
Totals: 570 works, 1,520 credits, 557 assessments (546 AI and 11 user status rows),
18 notes, and 140 connections. Private archives and import evidence are in
`C:/BSAD6153/planning/reading_notes/case_briefs/`.

All five agreed statements in `db/queries.sql` ran in a read-only transaction.
Result counts were 10, 6, 10, 10, and 10. Query comments identify JOINs, GROUP BY,
and the publication-date filter. See `questions.md` for interpretation and the
running question list. The student's surprise explanation remains pending.

### Author follow-up queries — November 8, 2026

After the student expressed surprise, added queries 6 and 7 to investigate author
frequency without filtering ratings. Read-only execution returned 50 authors
with multiple works, sorted by count; two authors tied at three. Query 7 retained
both leaders and returned six author/work rows (five distinct works, one shared).
Checks confirmed all query-6 counts exceed one, its total-author count equals its
row count, and query 7 has no duplicate author/work pairs and only maximum-count
authors. Latest AI ratings include NULL rather than dropping unassessed works.
The surprise comment now records the user's reaction and corrects their initial
interpretation: the maximum number of 5/5 works per author was two, not one.

### Final Parts A–D audit — November 8, 2026

Connection check passed using the Session pooler. The original `ingest/load.py`
rerun added zero works, author credits, assessments, or connections. Before/after
verification confirmed all rows and audit timestamps unchanged across all five
tables. Counts remain 570 works, 1,520 credits, 557 assessments, 18 notes, and 140
connections. Source-field, supplied pilot/connection, and RLS checks passed; all
five connection unit tests passed. The existing incomplete-credit warning remains
documented and its original payload retained. The completed AI review log and
submission checklist are in [Milestone 2 PR #4](https://github.com/khoekstr/bsad6153-taylor/pull/4),
merged November 8, 2026. The screencast link remains to be added.
