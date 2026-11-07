# Data quality and coverage report

Measured November 7, 2026, for the personal AI reading and reflection library.

## Scope and evidence

This report audits the **504 works in the reviewed local OpenAlex selection** from
run `20261029T155716Z_d357540f`. It does not measure all OpenAlex records, full-text
article quality, live PostgreSQL contents, or an operating recommendation system.
The original download contained 500 selected works; the reviewed selection added
four. Counts below use 504 unless another denominator is stated.

Evidence:

- `data/raw/20261029T155716Z_d357540f/reviewed_selection.json`: selected IDs and source files.
- The original work responses referenced by that manifest (local files ignored by Git).
- [Measured results](data_quality_metrics.json): counts, distributions, missing-value examples,
  and all matching-title candidates, retained in the repository.
- [Quality-check script](../scripts/check_data_quality.py): reproducible measurements.
- [Selection configuration](../ingest/selection.json) and [data dictionary](data_dictionary.md):
  collection intent and field meanings.

Run from the repository root with the original local downloads available:

```powershell
.venv/Scripts/python.exe scripts/check_data_quality.py --as-of 2026-11-07 --output docs/data_quality_metrics.json
```

The check uses the actual loader's preparation function to validate and transform
the selected records. It makes no network calls or database changes. A reader with
only the public repository can inspect the metrics and code, but cannot reproduce
the full audit without the ignored raw files. Missing means absent, null, or empty
for the measured field. Author coverage below distinguishes raw entries from usable
credits that have both an author ID and a nonblank name.

## Measured completeness and validity

| Check | Result | Consequence |
|---|---|---|
| Selected works / unique work IDs | 504 / 504 | Meets the collection-size target; not proof of database loading. |
| Required papers represented | 12 of 12 IDs present | Required readings are included as metadata, not necessarily full text. |
| Missing abstracts | 16 / 504 (3.17%) | An agent cannot summarize these papers from an abstract. |
| Missing publication dates | 2 / 504 (0.40%) | Unknown dates must not be treated as old or newly published. |
| Missing DOIs | 35 / 504 (6.94%) | DOI-only joins or deduplication would miss these papers. |
| Missing direct PDF URLs | 174 / 504 (34.52%) | An open-access flag does not guarantee a direct PDF link. |
| Missing language / primary topic | 0 / 504 for each | Populated metadata does not establish classification accuracy. |
| No raw authorship entries | 9 / 504 (1.79%) | Source authorship coverage is incomplete. |
| No usable author credits after validation | 21 / 504 (4.17%) | Inner joins to authorships would exclude 21 works. |
| Raw / usable author credits | 1,595 / 1,516 | 79 incomplete credits are omitted from the prepared relation; raw metadata is retained. |
| Distinct IDs among usable author credits | 1,464 | Counts credited identities, not independently verified people or fetched profiles. |
| Loader preparation | Passed | Selected titles, work types, IDs, dates, years, abstract positions, and usable credit formats passed its checks. |
| Future dates / date-year disagreements | 0 / 0 | Checked against November 7, 2026, where dates are available. |

For example, `https://openalex.org/W2953522645` lacks an abstract in this snapshot.
An agent must disclose that limitation rather than invent a summary from the title.
The 21-work usable-credit gap is larger than the nine-work raw-entry gap because
some nonempty authorship lists lack usable identifiers or names. The loader emitted
an incomplete-credit warning during this audit; this is an observed limitation,
not a silently repaired source record.

## Uniqueness and relationship checks

There are **zero repeated selected work IDs** and **zero duplicate normalized,
nonempty DOIs**. The selected manifest is keyed by work ID, so this does not prove
that the original search responses contained no repeated encounters.

There are **nine matching-title pairs (18 works)** after case folding and whitespace
normalization. These are review candidates, not confirmed duplicates. For example,
`W4413427262` and `W4412505619` both have the title “AI agents vs. Agentic AI:
A conceptual taxonomy, applications and challenges.” Distinct versions or records
could otherwise be recommended as separate new evidence. Compare DOI, authors,
venue, and version before merging; never delete or merge solely by title.

Prepared credits are attached to selected works and deduplicated by work/author ID
within each paper by the loader. This verifies the prepared relationships only.
Database foreign-key enforcement, actual loaded counts, and rerun behavior still
require database verification. A successful preparation run does not prove those checks.

## Coverage and fairness check

**Question:** Could the collection or missing metadata systematically limit which
research perspectives the agent can recommend?

All **504 works (100%) are marked English and open access**. This matches the broad
search filters and makes the collection convenient for this reading workflow, but
leaves **zero non-English or non-open-access examples** for comparison. An agent
must describe recommendations as drawn from this selected library, not the best
research worldwide. Language is not evidence of an author's nationality, and
open access is not evidence of credibility.

The check also compares abstract availability across selection groups:

| Selection group | Works | Share of collection | Missing abstracts | Within-group missing rate |
|---|---:|---:|---:|---:|
| Applications | 149 | 29.56% | 6 | 4.03% |
| Foundations | 100 | 19.84% | 2 | 2.00% |
| Ethics | 90 | 17.86% | 2 | 2.22% |
| Governance | 70 | 13.89% | 2 | 2.86% |
| Models | 60 | 11.90% | 3 | 5.00% |
| Organizations | 23 | 4.56% | 0 | 0.00% |
| Required readings | 12 | 2.38% | 1 | 8.33% |

These labels describe **how a paper was selected**, not its verified subject or
mutually exclusive intellectual content. “Required” is a selection reason, not a
topic. Different group sizes partly reflect deliberately unequal search targets;
they do not establish the relative importance or research volume of those topics.

If recommendations require an abstract, all 23 organization selections remain
eligible, while 3 of 60 model selections and 1 of 12 required readings are excluded.
This is a measurable difference in eligibility, not proof that recommendations
already discriminate. Small groups make percentage comparisons especially unstable.
The system should preserve a visible “metadata only” option and disclose why it
cannot generate an evidence-based summary instead of silently hiding those papers.

Publication years span 2015–2026, with two unknown. **317 of 504 (62.90%)** have
publication years 2025 or 2026. That describes this snapshot's recency, not complete
coverage of current AI developments. There are 503 articles and one conference
paper; the selection does not represent the videos, newsletters, or personal
reflections also relevant to the intended workflow.

**Conclusion:** This check identifies representation and metadata-availability
gaps. It does not measure prediction bias, demographic parity, author demographics,
viewpoint diversity, or recommendation outcomes. No deployed ranking was evaluated.

## Required handling and remaining work

The current loader already preserves raw metadata, validates identifiers and key
fields, skips incomplete credits with a warning, and does not invent personal notes.
The following are requirements for downstream behavior, not claims of implemented
agent safeguards:

1. Keep unknown abstracts, dates, and ratings explicitly unknown. Label whether a
   summary is based on full text, an abstract, or metadata only.
2. Use left joins where author or personal-note records are optional. No note does
   not prove “unread”; an absent rating does not mean “disliked.”
3. Review the nine title pairs before treating them as independent readings or
   evidence. Retain source IDs and version provenance.
4. Disclose the English/open-access scope; evaluate expanded collection options
   before making broad claims. Do not infer demographic characteristics from names.
5. Repeat these counts after each refreshed selection. Monitor group coverage and
   missingness, then separately evaluate actual recommendation exposure and usefulness.
6. Verify loaded database counts, foreign keys, duplicate-free reruns, and read-only
   permissions separately. Those checks have not been performed for this report.

No source records were corrected or removed during this audit. Link accessibility,
full-text accuracy, author identity, and whether papers support particular claims
remain unverified. The report completes the local-data assessment, not the entire
database milestone.

## Connection to the implementation brief (Mirror)

The fairness check found that all 504 library records are English and marked open
access, with no comparison records outside those categories. An agent unaware of
this scope could present its recommendations as globally representative. Also,
16 papers lack abstracts, and abstract coverage differs across selection groups;
silently excluding them could shape what ideas are surfaced. Recommendations should
disclose scope and missing evidence, preserve metadata-only candidates, and remain
subject to human review. These are measured coverage gaps, not proven prediction bias.
