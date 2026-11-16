# evals/

How you prove your system gives correct answers.

| Week | File | What it does |
|---|---|---|
| 3 | `golden_questions.csv` | 15+ questions with columns `id, question, category, reference_sql, correct_behavior, source` |
| 3 | `check_reference.py` | Runs every reference query as `app_reader` and confirms each one succeeds |
| 5 | `run_evals.py` | Asks your chatbot every golden question; records answer, tool calls, tokens, cost, time, and the reference result |
| 5&ndash;7 | `results/weekN.csv` | One results file per evaluation run, graded by you |

Reference answers are SQL, not fixed values, because your data keeps syncing.

## Part F: implemented November 14, 2026

The agreed set has 15 questions: 12 live SQL references and three `should_decline`
cases (unsupported author trustworthiness, media attention, worldwide consensus).
Exactly eight are marked `baseline`; the others are marked `other` as required by
the assignment, including later questions developed with the owner.

### Baseline provenance

| Golden question | Existing source in `docs/questions.md` |
|---|---|
| Q01: high-relevance articles without recorded reading | Initial query 1; `db/queries.sql` question 1 |
| Q02: recent high-relevance articles | Initial query 3; SQL question 3 |
| Q03: recover my notes | Running-list question “Can I return to earlier articles and recover my thoughts?”; also the Week 1 reflection |
| Q04: connections to articles with notes | Initial query 4; SQL question 4, extended to return the actual notes |
| Q05: category coverage | Initial query 2; SQL question 2, extended to include zero-count categories |
| Q06: authors with 5/5 articles | Initial query 5; SQL question 5 |
| Q07: authors appearing repeatedly | Author follow-up 6; SQL question 6 |
| Q08: works by the most represented authors | Author follow-up 7; SQL question 7, retaining all tied leaders |

### Running the checker

From the repository root, with the existing dependencies installed:

```powershell
python evals/check_reference.py --validate-only
python evals/check_reference.py
python evals/check_reference.py --output data/evals/reference_after_syncs.json
```

Only `APP_DATABASE_URL` is accepted, with no administrator fallback. Both database
user and session user must be `app_reader`. All questions use one repeatable-read,
read-only transaction, Central time, and timeouts. Savepoints let later questions
run even after a failure; prepared execution rejects multiple statements. Every
answerable query must return at least one row. SQL errors, empty results, invalid
CSV structure, role errors, and connection failures produce a nonzero exit code.
Decline rows are not executed and are not reported as chatbot passes: their
behavior still needs evaluation against the future chatbot.

Q11 intentionally returns a count and list, so zero pending articles is a valid,
nonempty answer `(0, [])`. Other empty query results fail the check and require
review; do not fill them with invented answers merely to make the checker pass.

Q09 requires source-signal migration 008 (already applied to the project database).
Citation counts are stored snapshots; unknown check dates are explicitly unknown.
Q10 compares today plus the preceding 89 Central calendar dates against the prior
90 dates. It uses publication date and OpenAlex primary topic, with dated-period
totals as denominators (including unknown topics). It reports both counts and
percentage-point changes. This supports description of this selected library,
not a representative global trend or a claim of statistical significance.

Q03/Q04 contain private notes and assume the authenticated owner. The reader role
is not a substitute for application authentication; public visitors must never
receive these private answers. Q12 returns the last addition-producing successful
discovery and its counts. Run history does not preserve a durable list of inserted
article IDs per run, so the reference must not claim exact article titles.

### First live baseline

Saved November 14, 2026 at **14:01:49 Central**, as `app_reader`, in a read-only
snapshot. All 12 reference queries passed; three decline cases were correctly
left unexecuted. Result row counts:

| Question | Rows |
|---|---:|
| Q01 | 10 |
| Q02 | 10 |
| Q03 | 21 |
| Q04 | 10 |
| Q05 | 6 |
| Q06 | 10 |
| Q07 | 50 |
| Q08 | 6 |
| Q09 | 5 |
| Q10 | 55 |
| Q11 | 1 (30 pending articles in its list) |
| Q12 | 1 |

The full answers are in **`data/evals/reference_baseline.json`**, ignored by Git
because they contain personal notes. The checker never overwrites a snapshot.
Each snapshot includes the question-file hash, per-query hashes, evaluation time,
column names, result rows, and pass/fail status. Baseline question-file SHA-256:
`35e8291b408012270b3cf7da7620c7990731069cc98b62806b2190d9cbb71476`.
Reference truth is still recomputed from SQL, not taken from the baseline file.

Seven checker tests passed, including live read-only checks that reject a
data-modifying CTE and multiple statements, continue after errors, fail empty
results, and accept an explicit zero-pending answer. Tests also verify CSV
requirements and rejection of an administrator connection before reference SQL.

```powershell
python -m unittest evals.test_check_reference -v
# Include reader-only database safety tests:
$env:REFERENCE_TEST_DATABASE = '1'
python -m unittest evals.test_check_reference -v
```

For Part G, wait for at least two additional scheduled syncs after this baseline,
save another snapshot, and compare answers using unchanged query hashes. Record
which runs actually added data versus same-day no-ops. Moving calendar windows
or later assessments can change answers independently of sync; identify those
causes separately. This baseline does not complete the later comparison or test
the future chatbot's refusal behavior. No sync was started to produce it.
