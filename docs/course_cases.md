# Course case references

The November 8, 2026 import covers all 64 source links in the course case
instructions: weekly pairs, alternates, education/science, and optional classics.
There are 63 distinct works across 42 cases. The NBER and Atlanta Fed references
to Firm Data on AI share one work; both references are retained in its raw data.

These are manual reference-file imports (`source='upload'`), with paths to saved
reference metadata. This does not imply a full-text download. Four works retain
previously verified OpenAlex identifiers; unverified search candidates are not
used as identifiers. Unknown authors and publication dates are not invented.

All 63 works have an AI assessment with `review_basis='excerpt'`: the excerpt is
the user-supplied course brief summary. Assessments include categories, personal
relevance ratings and reasons, summary, evidence limitations, and provenance.
Source-level assessments may share a case-level summary covering multiple links
or dates; they do not establish that each individual link supports every claim.
Novelty and estimated reading time remain unknown. Personal reading statuses,
ratings, favorites, and notes are not inferred.

There are 32 case-level comparisons, expanded into 80 source-to-source links.
Every imported work participates. All eight weekly success/failure pairs are
included, with relevant alternate and classic comparisons. Links use
`related_topic`, `proposed_by='ai'`, `review_basis='excerpt'`, and
`review_status='suggested'`. Suggested means an immediately usable AI
interpretation, not a request for user review. Explanations name the theme and
contrast; evidence fields retain both summaries and their limitations.

Success/failure labels come from the course framing. They are not independent
fact checks, causal findings, or head-to-head tests. Several sources about one
case must not be counted as independent replications. Structured course metadata
is retained in `works.raw.course_case`.

Private authoring, batch, import, readable report, ID mapping, and verification
files are in `C:/BSAD6153/planning/case_library/`. The import uses parameterized
queries, parent-first loading, unique import keys, and one transaction. It checks
assessment and connection fields against the saved batch and preserves existing
rows, including their audit timestamps. The original abstract-only loader is
unchanged; course excerpts use this separate, explicitly labeled import.
