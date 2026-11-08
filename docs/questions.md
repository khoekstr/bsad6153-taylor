# Running question list

Decision: what AI material should I read next, given my interests, available time,
and what I have already consumed? Based on `baseline_log.md` and subsequent user
discussion. Updated November 8, 2026. This list seeds Milestone 3.

## Five initial queries and two author follow-ups

| Query | Question | SQL features | Live result |
|---|---|---|---|
| 1 | Which 10 AI-rated 5/5 articles have no recorded reading activity? | JOIN, anti-match, LIMIT | 10 rows |
| 2 | How many distinct works belong to each AI-assigned category? | GROUP BY, array expansion | Learning 252; Technology 219; Work 186; Society 172; Information 112; Discovery 40 |
| 3 | Which 10 highest-rated articles were published in the last 90 days? | JOIN, publication-date filter, LIMIT | 10 rows |
| 4 | Which articles connect to articles I have written notes on, highest AI rating first? | Multiple JOINs, LIMIT | 10 connection pairs |
| 5 | Which authors have the most AI-rated 5/5 articles? | JOIN, GROUP BY, LIMIT | Two authors lead with 2 each; remaining displayed authors have 1 |
| 6 | How many authors have more than one work, ordered by most works? | GROUP BY, HAVING, window COUNT | 50 authors: 2 have three works, 48 have two |
| 7 | What works belong to the author with the most works? | JOINs, GROUP BY, maximum comparison | Two tied leaders; six author/work rows representing five distinct works |

Queries in `db/queries.sql` use the latest AI assessment per work. They address
the baseline concerns of search effort, narrowing interests, staying current,
connecting prior reading, and discovering sources worth exploring, respectively.
Author frequency does not measure reputation.

The live run used November 8, 2026 in America/Chicago. Query 3 covered August 11
through November 8 inclusive. Unknown publication dates are excluded. Private
full results: `C:/BSAD6153/planning/case_library/query_results.json`.

Category counts overlap because works may have several categories. Learning is
the largest AI-assigned category, not necessarily the user's favorite. Query 4
displays pairs: an article can recur when linked to different noted articles.
Multiple notes per work do not multiply rows. Query 1 excludes works with notes
even if reading status is unknown; absence of activity is not proof of nonreading.

The student expressed surprise at the lack of repeated 5/5 recommendations and
requested queries 6 and 7 to investigate. Their initial reading was a maximum of
one; the actual maximum was two (Pengcheng Chang and Qiuhan Zhu). The SQL comment
records both the reaction and correction rather than repeating the incorrect count.

The follow-up queries find 50 authors with multiple works. Ismaila Temitayo Sanusi
and Thomas K. F. Chiu tie at three each; the other 48 have two. Query 7 includes
both tied leaders and their latest AI ratings, including one unassessed work.
They coauthored one work, so six author/work rows represent five distinct works.
These are counts within this collected library, not career publication totals.
The author queries identify authors by OpenAlex ID when available, falling back
to normalized names; missing author credits and identity errors limit coverage.
Private follow-up results: `C:/BSAD6153/planning/case_library/author_query_results.json`.

## Deferred and currently unanswerable questions

- Where do AI recommendations disagree with my reactions? Deferred as too
  advanced for these initial queries; qualitative notes are not numeric ratings.
- Which recommendations use abstracts versus summaries? Review basis is stored,
  but the question was not selected for the initial five.
- Which works repeat material versus provide contrasts? Connection suggestions
  exist, but no exhaustive duplicate-content analysis has been performed.
- What distinguishes weekly success and failure cases? Course comparisons exist;
  causal conclusions need stronger evidence than supplied summaries.
- What is genuinely new to me? Requires fuller consumption history and reliable
  novelty assessments.
- What can I read in the time available? Reading-time estimates are missing.
- Which sources are trustworthy, expert-recommended, or human-reviewed? Author
  counts and AI evidence descriptions cannot establish these properties.
- Are recommendations improving after feedback? Requires later rounds and
  comparable reactions; automatic adaptation is not yet implemented.
- Which articles offer solutions rather than just describing problems? Raised
  in the user's initial notes; no structured field captures this distinction.
- Can I return to earlier articles and recover my thoughts? Notes are stored;
  a user-facing search interface remains future work.
- What are AI costs, future costs, and break-even points? Raised in the DBS note;
  the necessary project financial data are not systematically modeled.
- What measurable thresholds should determine scaling, revising, or stopping
  pilots? Raised in the Ford and Ableneo notes; optimal thresholds require
  project-specific outcome, cost, and benefit data.
- How should historical alternatives, false denials, and unequal group effects
  shape pilot decisions? Raised in the Ford note; comparative data are missing.
