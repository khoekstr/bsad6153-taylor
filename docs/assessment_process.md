# Abstract-only AI assessments

For the separate November 8 addition of 63 assessments based on course brief
excerpts, see [course cases](course_cases.md). The original abstract-only pass
described below remains unchanged.

Also on November 8, all nine articles from the user's initial reading list were
matched to existing works by DOI. Eight already had AI assessments. The remaining
article, *The global landscape of AI ethics guidelines*, received an explicitly
excerpt-based assessment using the supplied reading-list summary. Its original
abstract remains unchanged. Thus 22 of the original 504 works remain without any
AI assessment, while 23 still lack an abstract-based assessment. Seven verbatim
personal notes were recovered separately; no notes were supplied for items 8–9.

The initial assessment pass was completed in chat on November 7, 2026 using the
user-approved pilot rubric. No external AI API or full-text downloads were used.
The user authorized completing the batch; the additional outputs have not been
individually reviewed by the user.

## Coverage and meaning

- 481 works assessed: 10 pilot records and 471 additional records.
- 23 works left unassessed: 16 missing abstracts, five fields containing only a
  title, citation, or status, and two fields containing article bodies instead
  of usable abstracts.
- All 504 source works remain in the database. Missing assessments are unknown,
  not zero-value ratings.
- Value scores describe predicted personal relevance, not research quality:
  1 = little apparent value, 2 = peripheral, 3 = relevant but indirect,
  4 = strong fit, 5 = directly central to the user's questions.
- Each assessment includes categories, a summary, a relevance/value explanation,
  evidence limitations, review basis, context, reason, and model provenance.
- Novelty ratings and estimated full-paper reading times remain null because
  the available evidence does not support them. Personal reading status,
  favorites, return flags, and notes are not inferred. Work connections were
  generated in a separate authorized comparison pass; see `connections.md`.

The private JSON batches and readable `completed_assessments.md` report are in
`C:/BSAD6153/planning/assessments/`, outside the course repository. The
`unassessed_records.json` manifest identifies each exception and its reason.
Raw OpenAlex files were not edited. Distinct OpenAlex records may represent
versions of the same paper or duplicate abstracts; they are not independent
research evidence. Abstract review does not authenticate publications or verify
every reported result.

## Repeatable imports and later updates

`ingest/load.py --assessments PATH` imports saved assessments after their parent
works. It validates each abstract hash against the source and stored abstract,
then uses a stable batch/item import key to skip an already imported assessment.
Reusing the same batch does not spend AI compute or create duplicate rows.

For weekly updates, first identify new works with usable abstracts and no prior
AI assessment. Assess only those pending works using the same documented rubric,
save the results in a new private batch, and import that batch. A deliberate
reassessment needs a new batch ID and a reason; it adds history rather than
overwriting earlier judgments. If the abstract changes, review the changed
source before reassessing. The existing Milestone 2 loader skips existing works;
updating their source fields belongs to the Milestone 3 sync implementation.

This is the documented workflow, not an implemented automatic weekly assessment
service. The loader imports saved output; it does not call an AI model. Moving to
an API later should preserve the rubric, provenance, abstract hash, and stable
import keys.

## Query interpretation

For future queries, select the latest AI assessment per work before aggregating
ratings, since the schema allows assessment history. Count missing assessments
separately, and avoid multiplying assessment rows by author credits in joins.
An AI suggestion is distinct from a user's own assessment. See
`load_verification.md` for live import and rerun evidence.
