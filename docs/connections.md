# Initial AI-suggested work connections

November 8 addition: [course cases](course_cases.md) contribute 80 excerpt-based
source connections representing 32 case comparisons. The database now contains
140 connections. The initial abstract-based pass below remains unchanged.

Completed November 7, 2026: 60 connections across 61 works. All 46 works with an
AI value rating of 5 have at least one connection, along with 15 selected related
works. This is the focused initial pass discussed with the student, not an
exhaustive all-pairs review of the entire library. Other works can acquire
connections in later passes; absence of a link does not mean no relationship exists.

| Relationship | Count | Meaning |
|---|---:|---|
| supports | 13 | A finding or argument is consistent with another; not proof or necessarily replication. |
| challenges | 9 | A counterpoint or boundary condition, with differences in populations and outcomes explained. |
| extends | 13 | Adds a context, method, or conceptual lens; not a claim of citation or publication order. |
| overlaps | 2 | Likely repeated material or related versions; not independent supporting evidence. |
| related_topic | 23 | Useful paired reading without a stronger evidence claim. |

The suggestions were authored in chat after comparing supplied abstracts. Each
record has two source foreign keys, a relationship type, a specific explanation,
paraphrased evidence from both abstracts, and limits on the comparison. Both
source abstract hashes are retained in the private import batch and checked
against source files and the database. No external AI API or full-text downloads
were used. The private batch records the method, scope, date, and available model
provenance.

All records have `proposed_by = 'ai'`, `review_basis = 'abstract'`, and
`review_status = 'suggested'`. The student explicitly said no review is needed.
Suggested labels an AI interpretation and **does not gate display or use**.
Accepted/rejected remain available in the schema but are optional, not a required
queue. Personal comments were left null.

## Direction and query interpretation

For supports, challenges, and extends, read the explanation as the from-work's
relationship to the to-work. Related-topic and overlap links are symmetric but
stored only once; search both endpoint columns when listing a work's connections.
Do not create a second reverse row for these types. Avoid counting multiple
author credits or assessment-history rows as additional connections in joins.

Examples of the distinctions recorded:

- Better evaluated stories and lower self-perceived creativity concern different
  outcomes. Their connection is a qualified counterpoint, not a direct contradiction.
- Helpful AI tutors and poorer later unaided performance can coexist; tutor
  safeguards, learning context, and measurement timing matter.
- Two agent-taxonomy records and two marketing-study records have strongly
  overlapping abstracts. They remain separate source records, with likely overlap
  flagged rather than silently merged or counted as independent evidence.

## Files and repeatable loading

Private files, outside the course repository:

- `C:/BSAD6153/planning/assessments/connections.json`: saved import batch.
- `C:/BSAD6153/planning/assessments/work_connections.md`: readable explanations.
- `C:/BSAD6153/planning/assessments/connections_load_snapshot.json`: rerun fingerprint.

Run from the project folder:

```powershell
.\.venv\Scripts\python.exe ingest/load.py --connections C:/BSAD6153/planning/assessments/connections.json
```

The importer uses bound query parameters, checks both source abstracts, and skips
stable unique connection keys. Keys do not depend on wording or batch name, so
rephrasing or reimporting a relationship does not create another row. Existing
rows, statuses, and user comments are not overwritten. Deliberate edits need an
explicit update workflow; there is no automatic connection revision/history feature.

Five offline validation tests passed, covering direction, symmetric duplicates,
missing/changed source evidence, self-links, and AI-only scope. Live loading inserted
60 connections; the second load inserted zero. Field verification matched the saved
batch to both parents and all imported fields. A fingerprint across all five tables
confirmed identical rows and timestamps before and after the rerun. Source counts
remain 504 works, 1,516 author credits, and 481 assessments; personal notes remain empty.
