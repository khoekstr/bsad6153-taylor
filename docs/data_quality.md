# Data quality and coverage report

**Parts E–H, ready for review.** Measured November 15, 2026, at 10:07:17 a.m. Central.

## Scope and evidence

This report measures the live PostgreSQL reading and reflection library. It replaces the earlier local-download report in this same file. The earlier report and its metrics describe a different population and should not be treated as current database measurements.

All measurements below came from one consistent, read-only transaction connected as `app_reader`. The supporting queries are in [db/quality_checks.sql](../db/quality_checks.sql), labeled QC01–QC09. The measurement date appears beside each result. The private local result snapshot is `data/evals/quality_2026-11-15.json`; no personal notes are reproduced here.

To repeat the audit, connect using `APP_DATABASE_URL`, begin a `REPEATABLE READ READ ONLY` transaction, set the timezone to `America/Chicago`, record `transaction_timestamp()`, and run the queries. Counts will change as the library changes.

## Row counts

Query QC01 counts stored rows, not distinct articles mentioned in assessments or notes.

| Table | Rows | Measured |
|---|---|---|
| works | 581 | 2026-11-15 |
| authorships | 1557 | 2026-11-15 |
| reading_notes | 21 | 2026-11-15 |
| work_assessments | 568 | 2026-11-15 |
| work_connections | 140 | 2026-11-15 |
| sync_state | 1 | 2026-11-15 |
| sync_runs | 5 | 2026-11-15 |

QC08 separates source types. Records marked `upload` are locally supplied material; that label alone does not establish that a full article is available.

| Source | Works | Publication-year range | Unknown year | Published in current or previous year | Measured |
|---|---|---|---|---|---|
| openalex | 514 | 2015–2026 | 2 | 327 | 2026-11-15 |
| upload | 67 | 2026–2026 | 65 | 2 | 2026-11-15 |

## Missing important fields

QC02 counts null or blank text as missing. Rates use all works as the denominator, including locally supplied records; these are library coverage rates, not OpenAlex API failure rates.

| Field | Missing / total | Missing rate | Measured |
|---|---|---|---|
| abstract | 83 / 581 | 14.29% | 2026-11-15 |
| cited_by_count | 67 / 581 | 11.53% | 2026-11-15 |
| doi | 98 / 581 | 16.87% | 2026-11-15 |
| is_retracted | 67 / 581 | 11.53% | 2026-11-15 |
| language | 66 / 581 | 11.36% | 2026-11-15 |
| metadata_checked_at | 581 / 581 | 100.00% | 2026-11-15 |
| pdf_url | 243 / 581 | 41.82% | 2026-11-15 |
| primary_topic | 67 / 581 | 11.53% | 2026-11-15 |
| publication_date | 67 / 581 | 11.53% | 2026-11-15 |
| publication_name | 69 / 581 | 11.88% | 2026-11-15 |
| title | 0 / 581 | 0.00% | 2026-11-15 |

Missing citation counts are unknown, not zero. Unknown retraction status is not evidence that a paper has never been retracted. Publication name, citation counts, and retraction flags help a reader judge context; none proves credibility. Missing direct PDF links do not prove inaccessible full text.

No recorded metadata-check date means article-level verification time is unknown. A successful discovery run does not mean all older records were refreshed. Do not backfill check dates with migration or report dates.

QC03 checks assessments separately. Multiple assessments may belong to one work. A missing rating does not mean low value, and an empty category list may be intentional.

| Assessment measure | Count | Measured |
|---|---|---|
| Assessments with missing value rating | 12 | 2026-11-15 |
| Assessments with null or empty categories | 18 | 2026-11-15 |
| Works with no assessment | 28 | 2026-11-15 |

The intended workflow should assess newly added works. Unassessed works should remain visible as pending; recommendations limited to assessed works would otherwise silently exclude them.

## Duplicates and inconsistent values

QC04 measures duplicate groups. DOI matching removes common DOI prefixes and normalizes case; titles are normalized for case and whitespace.

| Duplicate check | Groups | Measured |
|---|---|---|
| openalex_id | 0 | 2026-11-15 |
| normalized_doi | 0 | 2026-11-15 |
| normalized_title | 9 | 2026-11-15 |
| work_author_id | 0 | 2026-11-15 |

Matching titles are candidates for review, not confirmed duplicate articles. Distinct versions may have different IDs. Compare identifiers, authors, venue, and version before merging. The natural-ID check excludes missing IDs; missing optional identifiers are not duplicates.

QC05 checks the following values. Nulls are handled as missingness above, rather than counted as out-of-range values.

| Check | Flagged rows | Measured |
|---|---|---|
| future_publication_date | 0 | 2026-11-15 |
| date_year_disagreement | 0 | 2026-11-15 |
| negative_citations | 0 | 2026-11-15 |
| invalid_value_rating | 0 | 2026-11-15 |
| invalid_categories | 0 | 2026-11-15 |
| nonpositive_reading_minutes | 0 | 2026-11-15 |
| invalid_author_order | 0 | 2026-11-15 |
| self_connection | 0 | 2026-11-15 |
| work_update_before_first_seen | 0 | 2026-11-15 |
| sync_finish_before_start | 0 | 2026-11-15 |
| negative_sync_counts | 0 | 2026-11-15 |

These checks establish consistency for the tested rules, not factual accuracy of source metadata. Dates are evaluated in America/Chicago; timestamp ordering is compared as stored instants. Future publication dates would require review rather than automatic deletion.

## Relationships and orphans

QC06 checks each child relationship and also measures works without author credits.

| Relationship check | Flagged rows | Measured |
|---|---|---|
| authorship_orphans | 0 | 2026-11-15 |
| note_orphans | 0 | 2026-11-15 |
| assessment_orphans | 0 | 2026-11-15 |
| connection_from_orphans | 0 | 2026-11-15 |
| connection_to_orphans | 0 | 2026-11-15 |
| works_without_authors | 85 | 2026-11-15 |

QC09 confirmed foreign keys from authorships, reading notes, and assessments to works, and from both ends of work connections to works. They use the default NO ACTION deletion behavior: deleting a referenced parent is rejected instead of leaving an orphan. A work without author credits is a metadata gap, not an orphan. Use left joins when author coverage is optional.

## Coverage and fairness

QC07 measures language and open-access coverage, including unknown values.

| Recorded language | Open access | Works | Missing abstracts | Measured |
|---|---|---|---|---|
| en | true | 514 | 16 | 2026-11-15 |
| en | unknown | 1 | 1 | 2026-11-15 |
| unknown | unknown | 66 | 66 | 2026-11-15 |

**Concrete risk:** The table above shows that every known language is English, with no identified non-English comparison group (QC07; measured 2026-11-15). If asked “What do researchers worldwide think about AI?”, the chatbot could mistake this selected library for global consensus and omit research perspectives outside its collection. Unknown language must remain unknown; it must not be silently classified as English. Language also does not identify an author’s nationality.

The same table shows that abstract availability is concentrated in records marked open access, while records with unknown access lack abstracts (QC07; measured 2026-11-15). An abstract-required recommendation filter would systematically hide the less complete records, including material the user intentionally saved. Preserve a metadata-only route and explain when the stored material is insufficient to answer.

For this personal research workflow, relevance and usefulness matter more than broad popularity alone. Incoming citations can help find influential work, but should not become a proxy for truth or personal value. Answers about trends should be labeled as trends within this library. The golden-question decline cases cover unsupported author-credibility, media-coverage, and global-consensus claims.

This is a coverage check, not a measurement of demographic bias or deployed recommendation outcomes. It does not infer personal characteristics from author names.

## Decisions: clean, reject, or leave alone

- **Clean for comparison:** Normalize DOI prefixes, case, and title whitespace in the audit queries. These transformations do not overwrite stored source values. No records were edited or deleted during this audit.
- **Reject invalid data:** The loader validates required fields and omits incomplete author credits rather than inventing identities; database constraints enforce identifiers, rating ranges, relationship rules, and allowed categories. This report does not claim a newly measured count of rejected source records.
- **Leave matching titles alone:** Review version and identity evidence before merging candidates. A matching title alone is insufficient.
- **Leave unknowns explicit:** Do not invent abstracts, dates, citations, source reputation, or verification times. Preserve locally supplied references even when their bibliographic metadata is incomplete.
- **Preserve user meaning:** No reading note does not prove unread; no assessment does not mean unimportant. Queue unassessed works for assessment rather than silently filtering them out.
- **Keep the assessment changes:** Relevance/value remains the assessment focus. Novelty and evidence-assessment ratings were removed in prior work; useful narrative context was preserved. That was an earlier change, not a cleanup performed by this audit.

## Limits and next actions

Review matching-title candidates and enrich incomplete records only where reliable evidence is available. Repeat this audit after further ingestion and compare the dated results. The separate [sync test report](sync_tests.md) documents recovery and rerun tests; these quality counts alone do not prove failure recovery.

This report supports the implementation brief’s goal of exploring research and connecting it to personal reflections. It does not certify article credibility, full-text availability, source classification accuracy, or chatbot answer quality. The Part H sections below describe lineage, ownership, freshness, and this week’s operational findings.

## Part H: lineage and quality controls — November 16, 2026

| Stage / destination | Transformations and quality consequence |
|---|---|
| OpenAlex API to raw response | `ingest/fetch.py` retrieves `/works` with bounded retries and stores raw response JSON locally. Selected originals are retained in `works.raw`; runner-local files are not a durable archive. |
| `ingest/sync.py` candidate selection | Apply topic priority, exclusion and pause terms, English/open-access eligibility, nonfuture known dates, request/page budgets, and the UTC-day gate. Normalize title text and DOI matching keys; compare IDs, DOI keys, and titles against the library. These filters shape coverage and can exclude distinct same-title versions. |
| Shared preparation to `works` | Validate source identifiers, title/type, dates/years, and abstract positions; parse dates; reconstruct abstract text from ordered word positions; map nested topic, open-access, PDF, and landing-page fields. Keep original JSON and missing values. Discovery inserts unseen IDs; targeted refresh changes existing source-owned fields only when content differs, ignoring transport-only updated_date/relevance_score. |
| Generated source fields | Extract valid nonnegative incoming citation counts, trimmed primary-source names, and boolean retraction flags from raw metadata. Unknown stays NULL. Revised sync timestamps saved source snapshots; historical dates are not fabricated. |
| Nested authors to `authorships` | Validate IDs/names, skip incomplete credits with warnings, deduplicate author IDs, and derive order from the source array. Link to local work_id. Explicit refresh reconciles credit additions, changes, and removals in one transaction. |
| `sync_state` | Save cursor/preference progress, completed UTC day, latest IDs and counts with committed data. Separate targeted-refresh state does not consume discovery progress. |
| `sync_runs` | Commit an initial unfinished audit row, then finalize success and committed counts with data. On failure roll back data/progress and save sanitized failure evidence separately when connectivity permits. Missing execution or initial connection failure may create no row. |
| Local references and `reading_notes` | Locally supplied references use `works(source=upload)`. User notes/questions reference a work; migration 004 appends existing question text into notes. These are private user inputs, not API-generated facts. |
| `work_assessments` | Separately saved AI output is validated against source/stored abstract hashes and provenance, mapped to work_id, and imported with stable keys. Historical evidence/novelty narratives are preserved as text; active ratings focus on relevance/value. Optional numeric page-range enrichment estimates full-article reading time and records assumptions. User assessments are distinct from AI output. |
| `work_connections` | Separate saved suggestions validate both abstracts, endpoint IDs, allowed types, and provenance; map endpoints to work IDs; and use repeatable import keys. Suggestions are not independently verified relationships. |

See [the data dictionary](data_dictionary.md#part-h-record-lineage--november-16-2026)
for the detailed mappings and validation rules. Scheduled discovery does not call
an AI model or generate notes, assessments, or connections. Read-only quality and
golden-reference checks inspect the resulting tables without altering them.

## Part H: change log and implications

| Observed / documented date | Finding and consequence |
|---|---|
| November 14, 2026 | Existing source metadata was exposed as citation/publication/retraction fields; historical verification timestamps stayed NULL. Do not present unknown freshness or source signals as a credibility guarantee. |
| November 14, 2026 | Novelty and separate evidence-assessment fields were removed while narrative context was retained. Relevance/value remains the rating used for this personal library. |
| November 13–15, 2026 | GitHub started scheduled jobs late. The completed-day guard uses UTC, so a late local-evening addition can cause the following local day's attempt to do no work. A green run is not proof of additions or refreshed old records. |
| November 14, 2026 | Isolated failure tests confirmed rollback/recovery and an explicit simulated title/citation update. They did not establish that production metadata had changed at the source. |
| November 15, 2026 | QC01–QC09 measured the mixed live library rather than the earlier local download. Missing metadata and English-only known-language coverage affect what recommendations can responsibly claim. Counts above retain this measurement date; they are not silently relabeled as November 16 values. |
| November 16, 2026 | The post-sync golden check passed all 12 references. Four answers changed; the pending AI queue grew from 30 to 35, and five new pending IDs match the November 15 addition time. The recent-reading answer also changed as its calendar window moved. See the detailed evidence in sync_tests.md. |
| November 16, 2026 | Source deletions have not been demonstrated by these tests and are not automatically reconciled. Do not interpret absence from a bounded search as grounds to remove a stored work or its notes. |

The assessment queue is a separate issue from metadata sync. Part E's count of
works with no assessment of any kind (QC03) and Part G's count with no **AI**
assessment (Q11) use different definitions as well as different snapshot dates;
they should not be compared as if they measured the same backlog.

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
