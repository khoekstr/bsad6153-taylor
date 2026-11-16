# Data dictionary: personal AI reading library

Prepared October 29, 2026; updated through November 16, 2026. This document
describes source metadata, the personal library, and sync operations. Historical
download observations retain their original dates and scope. The schema is defined in
`db/schema.sql` and `docs/schema.md`; live database loading and duplicate-free
reruns are verified in `docs/load_verification.md`.
Examples and observations below come from the local collection, not invented records.

## 1. Source and collection scope

- **API:** OpenAlex; base URL: `https://api.openalex.org`.
- **Endpoints used:** `GET /works` for title searches and topic searches;
  `GET /authors` for separate records linked by the works' author IDs.
- **Parameters:** `search`, `filter`, `per_page`, and `cursor`. General searches
  use `type:article,language:en,is_oa:true`; requested papers are handled separately.
  Reviewed `openalex_id` filters are now configured for future required-paper lookups.
- **Authentication:** `Authorization: Bearer <key>`. The script reads
  `OPENALEX_API_KEY` from local `.env`; `.env.example` contains only the blank name.
  Keys are not included in request URLs, raw records, or this document.
- **Documentation:** [API reference](https://help.openalex.org/api/),
  [authentication](https://help.openalex.org/api/authentication/),
  [pagination](https://help.openalex.org/api/paging/),
  [filters](https://help.openalex.org/api/filtering/),
  [work fields](https://help.openalex.org/data/works/attributes/), and
  [common entity fields](https://help.openalex.org/data/common-attributes/).
- **Terms:** [OpenAlex Terms of Service](https://openalex.org/OpenAlex_termsofservice.pdf)
  (revised October 2, 2026); [data licensing statement](https://help.openalex.org/data/how-its-built/)
  and [CC0 explanation](https://creativecommons.org/publicdomain/zero/1.0/).

The first successful run, `20261029T155716Z_d357540f`, selected **500 unique works**
and retrieved **1,451 distinct author records**, using 51 API requests. It saved
about 39.55 MB in 54 files before the subsequent review files were added.
Nine selected works had empty/missing authorships; all author IDs requested in that
run were returned. This does not prove the authorship metadata is complete or correct.

The later reviewed selection contains **504 works**, including all 12 requested
research papers. Four required works were added from already-downloaded search results;
two other previously unresolved papers were already in the selected 500. The original
run summary remains unchanged. Separate author retrieval has not been repeated for the
four additions, so the 1,451 count describes the original run, not a verified complete
author set for all 504 works.

Evidence, relative to the repository root:

- `data/raw/20261029T155716Z_d357540f/summary.json`: original counts and warnings.
- `data/raw/20261029T155716Z_d357540f/reviewed_selection.json`: reviewed IDs and provenance.
- `data/raw/20261029T155716Z_d357540f/reading_list.csv`: readable candidate list.
- `data/sample/openalex_sample.json`: one unmodified work and author excerpt for review.
- `ingest/selection.json`: six search categories, queries, and required-paper IDs.

Raw downloads are ignored by Git. One JSON response can contain many records;
one JSON file is not one article. Responses also contain unselected search candidates.
No full-text articles, PDFs, videos, or personal reading notes were downloaded.

## 2. What one record means

**Work:** One record describes one scholarly work as represented by OpenAlex,
such as an article; it contains bibliographic information and links rather than the
full article. A work record is a reading candidate, not evidence that the user read it.

**Author:** One record is OpenAlex's profile for a person credited with scholarly
work. Identity matching is automated and can incorrectly combine or split people;
the profile is not a verified personal account.

**Authorship:** One nested entry connects an author to a particular work, with
position and affiliation information. Validated credits populate the authorships
table; they come from nested works metadata, not from a third endpoint.

## 3. Important fields

The table lists **20 fields**. Types describe the JSON, not final SQL columns.
`[]` means an array; dotted paths identify nested fields. “Missing” includes absent
keys, null values, and empty arrays where applicable. Examples are observed values;
short objects are explicitly excerpts. These are snapshots, so counts can change.

| Resource / field | JSON type | Observed example | Meaning | Can be missing? |
|---|---|---|---|---|
| Work `id` | string | `https://openalex.org/W4400578758` | Source identifier for the work. | Required by this importer; invalid records skipped. |
| Work `display_name` | string/null | `Generative AI enhances individual creativity but reduces the collective diversity of novel content` | Title. | Yes upstream; blank titles skipped. |
| Work `doi` | string/null | `https://doi.org/10.1126/sciadv.adn5290` | External publication identifier. | Yes; not every work has a DOI. |
| Work `type` | string | `article` | OpenAlex's resource classification. | Expected; validate when loading. |
| Work `language` | string/null | `en` | Detected metadata language. | Yes; does not guarantee full-text language. |
| Work `publication_date` | string/null | `2024-07-12` | Publication date. | Yes; 2 missing in the original 500. |
| Work `publication_year` | integer/null | `2024` | Publication year. | Allow unknown; do not invent a date. |
| Work `abstract_inverted_index` | object/null | Excerpt: `{"Creativity":[0],"is":[1,142]}` | Words mapped to positions. | Yes; 16 missing/empty in the original 500. |
| Work `authorships[].author.id` | string/null | `https://openalex.org/A5011170431` | Link to an author record. | Yes; 9 works lacked authorships. |
| Work `authorships[].author_position` | string/null | `first` | Author's position on this work. | Allow unknown. |
| Work `open_access.is_oa` | boolean | `true` | OpenAlex reports an open copy. | Allow unknown on manual/other records. |
| Work `best_oa_location.pdf_url` | string/null | `https://www.science.org/doi/pdf/10.1126/sciadv.adn5290?download=true` | Link to an open PDF. | Yes; URL accessibility not tested. |
| Work `best_oa_location.license` | string/null | `cc-by` | Reported license for that copy. | Yes; unknown is not permission. |
| Work `biblio` | object with string/null members | Excerpt: `{"first_page":"eadn5290","last_page":"eadn5290"}` | Citation/page labels. | Members can be missing or nonnumeric. |
| Work `primary_topic.display_name` | string/null | `Creativity in Education and Neuroscience` | Provider-assigned subject label. | Allow missing; not our search category. |
| Work `updated_date` | string | `2026-10-29T09:56:32.521200` | Provider's last-change timestamp. | Preserve raw value; handle absent/invalid values. |
| Author `id` | string | `https://openalex.org/A5000934027` | Source identifier for the profile. | Required by this importer. |
| Author `display_name` | string | `Lee A. Fleisher` | Profile name. | Blank/missing names skipped by importer. |
| Author `orcid` | string/null | `https://orcid.org/0000-0003-2899-2294` | Linked researcher identifier. | Yes; never identify people by name alone. |
| Author `works_count` | integer | `748` | Works associated with this profile. | Expected; permit unknown on incomplete records. |

These interpretations use the official [work dictionary](https://help.openalex.org/data/works/attributes/)
and [common attributes](https://help.openalex.org/data/common-attributes/), checked
against our JSON. An open-access flag, topic, publication count, or citation count
is not a credibility rating.

## 4. Identifiers and relationships

Works use local bigint primary keys and a unique, nullable OpenAlex ID. OpenAlex
imports require that ID; uploads instead require a file reference and may leave
publication details blank. Milestone 2 skips existing imported rows rather than updating them.

The agreed design uses `authorships` for credits, without a separate author-profile
table. Each credit references a work and stores a name, optional OpenAlex author ID,
and optional positive author order. Source IDs are unique per work, not across all
credits. Downloaded author profiles remain raw evidence, not a fourth imported entity.
The loader derives order from the source authorship array; raw metadata retains
the provider's first/middle/last label and affiliation information.

The other three tables are `reading_notes`, `work_assessments`, and `work_connections`.
A work has multiple editable notes, at most one editable user assessment, and a history
of AI assessments. Personal value rating, favorite, current reading status, and revisit
intention live on the user assessment. AI rows store predicted value, summaries,
and explanations. Multiple categories are a controlled text list on assessments; user
choices override AI suggestions. Connections reference two different works. See
`schema.md` for the complete diagram, types, constraints, and privacy boundaries.

DOIs provide a second matching signal. Titles are not unique: versions, corrections,
and different publications can share wording. Do not merge solely by title or name.
OpenAlex IDs can be merged upstream; retain a mapping to a surviving ID and review
unexpected replacements rather than silently deleting local notes.

The original six search groups remain provenance in the local selection manifest,
not a works column. Library categories are Learning, Work, Information, Society,
Technology, and Discovery, distinct from `works.openalex_topic`. No lookup or linking
tables are used for categories. NULL personal categories means use the latest AI
suggestions; an empty list means the user explicitly chose none. The loader never
assigns library categories.

## 5. Update behavior

OpenAlex continuously ingests sources and its catalog evolves daily; older records
can gain corrected metadata, links, abstracts, citations, or different identity matches.
The source publication date is different from when OpenAlex discovers a work and
from when our library first collects it. [How OpenAlex is built](https://help.openalex.org/data/how-its-built/)

**Current behavior (November 16, 2026):** `ingest/sync.py` performs bounded,
preference-driven discovery using saved database progress. It inserts unseen works
and author credits, with at most five additions per completed UTC day. It skips
existing records during discovery. An explicit, reason-required `--refresh-id`
operation can update one existing OpenAlex work; it is not scheduled bulk refresh.

The active configuration uses free-access searches, not a source-update watermark.
The saved cursor is discovery progress, not proof that all source changes have
been consumed. Source deletions and ID merges are not automatically reconciled;
a missing response does not authorize deleting local records or notes. See the
Part H lineage and freshness sections below for current operational limits.

Store audit times as timezone-aware UTC timestamps. The observed provider timestamp
has no explicit offset; confirm its timezone convention before conversion and keep
the original string. A changed record is not necessarily a newly published article.

## 6. Observed surprises and consequences

These are findings from the download/review, not claims about what the student
personally expected. The student should review and explain the findings in their own words.

1. **Missing information despite accessible articles:** among the original 500,
   16 lacked abstracts, 9 lacked authorships, and 2 lacked publication dates.
   Summaries must state their evidence basis; missing values must not become invented facts.
2. **Page labels are not always page numbers:** the creativity paper uses `eadn5290`
   in both page fields. Subtracting these fields would not give a valid reading length.
3. **Exact titles can be ambiguous:** the downloaded searches returned multiple
   `Generative AI at Work` records, including journal and working-paper versions.
   Four duplicate work encounters were also skipped during the initial selection.
   Use IDs and version evidence rather than title-only deduplication.
4. **Shortened titles caused missed automatic matches:** the tutoring, deepfakes,
   and guardrails titles included subtitles in OpenAlex. Reviewed IDs now resolve
   those requested papers without relying on identical title strings.
5. **Dates may differ from a supplied citation:** the QJE version of `Generative AI
   at Work` is indexed with year 2024, whereas the supplied journal citation used
   2025. Preserve the source value and verify online/issue dates before citing it;
   do not silently overwrite it to match the supplied citation.
6. **Abstracts arrive as word-position mappings:** the creativity record starts with
   `Creativity: [0]`, not a ready-to-display paragraph. Reconstruction and missing-data
   handling are required before treating this field as readable text.

## 7. Data-use ethics check

**What do the terms allow and forbid: storage, display, commercial use, attribution?**
OpenAlex's explicit CC0 metadata statement supports copying, storing, displaying,
and commercial reuse without a copyright attribution condition (we will still credit
OpenAlex and link sources), but the service terms contain broad restrictions on
unauthorized reuse; this apparent tension needs clarification before public republication.
CC0 does not grant rights to third-party articles, images, trademarks, or private information:
check the particular copy's license before redistributing text/PDFs and follow service
access limits. [Data statement](https://help.openalex.org/data/how-its-built/),
[CC0](https://creativecommons.org/publicdomain/zero/1.0/),
[service terms, “Your Rights to Use the Service”](https://openalex.org/OpenAlex_termsofservice.pdf)

**Does the data describe identifiable people, and did they expect this use?**
Yes: names, ORCIDs, affiliations, and publication histories identify real researchers;
scholarly discovery is consistent with their public publication context, but we cannot
assume individual consent to every aggregation or automated judgment.
Use the records for finding research, not sensitive profiling or unsupported author rankings.

**What is the worst realistic harm if the copy leaked or were misread?**
Misidentified authors or unsupported credibility judgments could damage reputations or
mislead a reader; public metadata alone has lower confidentiality risk than the future
personal layer. A leak of that layer could expose private interests, criticism, unfinished
research ideas, and notes, so it must be kept separate from public catalog access.

**Who should read or change these records?**
The intended public catalog reader may read approved bibliographic fields, while only
the trusted ingestion process should update provider records; the owner alone should
access or edit private notes, ratings, and history through authenticated, limited permissions.
The course starts with a read-only website database role, so personal-note writes need
an explicitly scoped later design consistent with the course rules; these controls are
partly implemented: app_reader has SELECT-only access, while an authenticated
website and scoped personal-write role remain future work.

## 8. Personal fields are not API facts

Reading notes and questions, user ratings, reading status, favorites, and revisit
intentions are private user-generated data linked to works. AI relevance/value
assessments, summaries, and suggested connections are separately labeled outputs
with provenance and review basis. These tables are populated; the sync does not
produce their contents. An assessment does not establish that the user read a
paper. Locally supplied references use `source=upload`; their metadata must not
be represented as fetched OpenAlex facts.

## Full-article reading time

`work_assessments.estimated_reading_minutes` is a positive integer estimate for
the full article; NULL means unknown, never zero minutes. The optional text
`estimated_reading_basis` records the length source and assumptions. The initial
page-based enrichment uses 2 minutes per page for usable numeric OpenAlex page
ranges; it does not infer full-paper length from abstracts. See
[assessment process](assessment_process.md) for exclusions and the repeatable
preview/apply command. Existing assessments and their original review basis are
preserved; filling these fields updates the normal audit timestamp.


## Reading notes and questions

Personal questions stay within `reading_notes.notes` alongside the observations
that prompted them. The separate `questions` column was removed by migration
004, which appends any nonblank question text to notes before dropping it.
The project-wide running business-question list in `docs/questions.md` is unchanged.
## Part B sync progress (updated November 16, 2026)

`sync_state` has one row per named pipeline. Its JSON state records the completed
UTC day, discovery cursors, preference hash, last success time, latest result,
and latest added IDs. `last_updated_at` records when progress committed.
Per-run history is in `sync_runs`. Only the sync owner writes; app_reader reads.
Older state keys may remain but are not evidence of active refresh behavior.
For implementation details, see [sync implementation](sync_implementation.md).

## Revised discovery-only policy

Routine sync no longer maintains a refresh position or checks existing papers.
Old refresh fields, if present, are unused. Explicit one-article maintenance stores
its reason and result under a separate `refresh:<OpenAlex ID>` sync_state key.
Changed-abstract IDs in that result flag a need for reassessment; daily discovery
does not examine old abstracts or modify existing records.

## Part C run history (November 12, 2026)

`sync_runs` stores one attempted invocation per run_id, including start/finish,
status, fetched candidates, committed work insert/update counts, safe error,
and manual/schedule trigger. dry_run/mode/outcome prevent previews and skipped
runs from being treated as live discoveries. details holds numeric supplementary
counts, including proposed counts for previews. See [field definitions](sync_runs.md).
Lineage: sync entry point -> durable started row -> transactional discovery/data/
progress + successful final row; on failure data rolls back and the error row
is finalized separately. app_reader reads this table through scripts/status.py.

## Source signals — November 14, 2026

Migration 008 exposes saved OpenAlex metadata on works:

- cited_by_count: the number of other works citing this paper, not its reference count. Missing/invalid values remain NULL; zero is a known zero.
- publication_name: the primary source name (journal, conference, or repository), not an endorsement.
- is_retracted: OpenAlex's reported retraction flag; NULL means unknown, and false is not proof of reliability.
- metadata_checked_at: when a live sync saved the source snapshot. Existing snapshots and historical-file imports have unknown check dates (NULL). This is not the date the source last changed.

The first three values are derived from works.raw, preventing duplicate metadata
from drifting apart. Live discovery and changed-record targeted refreshes stamp
the date checked. No-change reruns preserve it. Routine discovery still does not
refresh existing papers; these are dated snapshots, not current credibility scores.
No source requests or manual sync are needed for the migration.

Novelty and separate evidence assessments are retired. AI summaries retain useful
qualifications; personal relevance/value remains the rating. Historical novelty
explanations are retained in assessment_context rather than active score fields.

Verification on November 14: migrations 007/008 were rehearsed on temporary
copies, then applied together in a transaction. All 568 assessment rows retained
their prior summaries and narrative notes. Of 581 works, 514 have citation counts,
512 publication names, and 514 retraction flags; all legacy check dates remain
unknown. app_reader can SELECT the new fields. The 35-test combined suite passed,
including temporary-table sync checks. An additional importer integration check
passed for current/legacy formats and duplicate reruns. No live sync was invoked.
The date stamp starts for new live snapshots after the sync-code PR is merged.

## Part H: record lineage — November 16, 2026

The following describes repository behavior, distinguishing the review branch
from the workflow already deployed on main. No new sync or database write was
performed to prepare this documentation.

1. **OpenAlex to retained response:** GitHub invokes `ingest/sync.py` using secrets
   supplied as environment variables. `ingest/fetch.py` requests `/works`, retries
   temporary failures with bounded backoff, validates responses, and saves raw
   JSON under the run's ignored `data/raw/sync_<run_id>` directory. Raw files on
   GitHub runners are local job files, not a durable published archive. The selected
   record's original JSON is also retained in `works.raw`.
2. **Response to selected candidates:** `search_preferences.json` supplies topic
   priority, pauses, exclusions, and budgets. Discovery checks English and open
   access, rejects future/unknown publication dates, normalizes text for exclusion
   matching and titles for deduplication, and normalizes DOI case/prefixes for
   duplicate detection. It compares source IDs, DOIs, and titles against stored
   works, sorts candidates by publication date and ID, and adds up to five. If
   preferred searches produce none, the fallback can add one eligible paper.
   These matching transformations do not rewrite the saved title or raw DOI.
3. **Selected work to `works`:** shared `ingest/load.py:prepare_record` validates
   work IDs, nonblank titles, types, dates, years, and abstract positions. It parses
   the date; reconstructs the abstract by sorting word positions and joining words;
   maps display_name to title, primary_topic to openalex_topic, open_access.is_oa
   to is_open_access, best_oa_location.pdf_url to pdf_url, and the primary landing
   page to source_url. It preserves optional missing values, source metadata, and
   raw JSON. Local IDs and audit timestamps come from the database. Discovery uses
   conflict-safe inserts. Explicit refresh compares actual fields/raw content,
   excluding transport-only updated_date and relevance_score from change detection.
   It updates changed source content while retaining the local work identity.
4. **Derived fields on `works`:** generated columns extract incoming citation
   counts only from valid nonnegative numeric source values, trim the primary
   publication name, and accept boolean retraction flags. Invalid/missing values
   remain NULL. These are source signals, not credibility assessments. Revised
   sync writes metadata_checked_at for saved snapshots; see the deployment caveat
   in the freshness section.
5. **Nested credits to `authorships`:** extract author ID/name, assign one-based
   order from the source array, warn and omit incomplete credits, validate IDs,
   and collapse repeated author IDs while retaining the first order. Conflicting
   names for the same ID are rejected. Link credits to local work_id. Explicit
   refresh reconciles inserted, changed, and removed credits transactionally,
   clearing moved positions before updates to avoid order conflicts. Separate
   author-profile downloads remain raw historical evidence, not another table.
6. **Progress and audit:** `sync_state` stores the preference hash, discovery
   cursors, completed UTC day, added IDs, and counts in the same transaction as
   data changes. Targeted refresh uses a separate state key. `sync_runs` first
   commits a conservative unfinished row, then commits successful outcome/counts
   with data/progress. Catchable failures roll back data/progress and finalize a
   sanitized failure row separately. A hard kill or connection loss may leave the
   unfinished row. If a database connection cannot be established, even the first
   audit row may be unavailable; consult Actions logs.
7. **Separate personal/AI paths:** locally supplied references become
   `works(source=upload)` and may have incomplete bibliographic fields. User notes
   and questions go to `reading_notes` via work_id, not through OpenAlex; migration
   004 preserves question text in notes before removing the separate field.
   Saved, approved AI batches go through `prepare_assessments`/`load_assessments`:
   validate abstract hashes, provenance, and personal-control restrictions; map
   source IDs to work_id; preserve historical qualifications in summary/context;
   and insert `work_assessments` using stable import keys. Optional page-range
   enrichment fills missing AI reading-time estimates using inclusive valid page
   ranges and two minutes per page, recording assumptions. It never treats an
   abstract's length as full-paper length. User assessments remain user judgments.
   Saved AI connection batches validate both source abstracts, distinct endpoints,
   connection type, and provenance; map endpoints to work IDs; and populate
   `work_connections` as suggestions with repeatable import keys. No assessment,
   connection, or private note is generated by the scheduled sync itself.

Database constraints enforce parent relationships and allowed values. The sync
owner writes; `app_reader` reads through restricted access. The current automated
assessment API remains future work.

## Part H: change log — November 12–16, 2026

- **November 14:** source signals were exposed from saved raw metadata, and novelty
  plus separate evidence-assessment fields were retired while useful narrative
  context was preserved. Existing metadata-check dates stayed unknown instead of
  being invented. See migrations 007/008 and the dated verification above.
- **November 13–15:** actual scheduled starts were delayed. A November 13 evening
  run was already November 14 UTC, so it consumed the next UTC day's allowance.
  Successful later attempts can therefore add nothing even on another local day.
- **November 14 safety tests:** a simulated citation/title change flowed through
  explicit targeted refresh; an identical refresh changed nothing. Interruption
  rolled back partial writes and recovery produced no duplicates. These were
  isolated tests, not observed source corrections in production.
- **November 15 quality snapshot:** the live library mixes fetched and locally
  supplied material. Missing metadata cannot all be attributed to OpenAlex.
  Matching-title groups need human review; unknown fields remain unknown. See
  the dated QC01–QC09 measurements in [data quality](data_quality.md).
- **November 16 evaluation:** after three additional scheduled executions, all
  twelve SQL references passed. Q02, Q10, Q11, and Q12 changed; pending AI
  assessments rose from 30 to 35, with the five new entries timestamped inside
  the November 15 addition-producing run. Q02 also changed because a paper aged
  out of its date window. See [sync tests](sync_tests.md) for exact evidence.
- **Deletion limits:** no source disappearance has been established by these
  checks. The pipeline does not reconcile deletions; a missing response leaves
  existing work and private records intact rather than silently removing them.

## Part H: freshness guarantee — November 16, 2026

**There is no finite worst-case freshness guarantee in the current design.**
The schedule is a request to attempt discovery, not a guarantee that a particular
paper will be present or current by a deadline.

- **Discovery cadence:** the trial requests 08:00 and 14:00 Central on November
  13–16, 2026 (`0 14,20 13-16 11 *`). Nominal gaps are six hours during the day
  and eighteen hours overnight. GitHub has delayed actual starts. The workflow
  additionally rejects scheduled execution at or after November 17, 00:00 UTC
  (November 16, 18:00 Central). An excessively delayed final attempt may therefore
  be skipped. No continuing schedule has been configured after this trial.
- **New-paper coverage:** only one discovery can complete per UTC day, with at
  most five additions. The budget is forty requests and two pages per topic.
  Priority topics, exclusion filters, language/open-access eligibility, and
  duplicate checks can keep a source record out indefinitely. This is a curated
  discovery library, not a complete source mirror.
- **Existing metadata:** routine discovery skips stored IDs. Citation counts,
  titles, links, abstracts, and retraction status can remain stale indefinitely
  unless an explicit targeted refresh is performed. Source deletions and merges
  are not automatically propagated. Publication date is not a freshness measure.
- **Assessments and personal material:** assessments run separately; pending work
  has no promised assessment deadline. Notes reflect user edits, not API sync.
  A changed abstract can require reassessment, but does not automatically replace
  historical judgments or private notes.
- **Honest timestamps:** `first_seen_at` means first stored locally;
  `last_updated_at` means a local row changed; `metadata_checked_at` records a
  source snapshot saved by the revised sync and is unknown for legacy snapshots.
  The revised timestamp-writing sync is on the review branch, not yet merged into
  the scheduled workflow on main. An unchanged refresh does not advance that
  timestamp. None of these fields promises that the source has not changed since.

Use `sync_runs` to distinguish the last attempt, last successful discovery, and
last run that actually inserted or updated works. Display stale/unknown status
rather than claiming every paper is current after a green workflow run. A finite
service guarantee would require a continuing schedule, monitored deadlines,
coverage and backlog controls, and a defined refresh policy; those are future
operational decisions, not features implemented by this documentation update.

## Part H: ownership and alerts

For this project, **Kara Taylor is the accountable owner** of the library, topic
preferences, credentials, and final review. In a company, a named data-engineering
owner would operate the pipeline, while the research/product owner would own
selection criteria, assessment quality, and acceptable freshness. The database
administrator would maintain permissions and recovery; the security owner would
handle credential exposure or unauthorized access.

The pipeline owner/on-call engineer should receive failures, unfinished runs,
repeated partial runs, and missed expected executions. The research/product owner
should be informed when delays or missing assessments affect recommendations.
Database or credential problems should also reach the administrator, with secrets
kept out of notifications. Escalate unresolved failures to the service owner.

Current evidence is GitHub Actions status/logs plus `sync_runs` and
`scripts/status.py`. Failed syncs exit nonzero; error text is sanitized. GitHub
email delivery depends on account notification settings and is not verified here.
There is no independent missed-run monitor or company on-call route configured.
A scheduler that never starts a job creates no database audit row, so checking
only failed rows cannot detect that condition. The company alert routing above
is a proposed responsibility model, not a claim that alerts were installed.
