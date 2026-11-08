# Milestone 2 readiness — November 8, 2026

## Parts A–D

- [x] Local DATABASE_URL uses the Supabase Session pooler on port 5432.
- [x] `.env.example` contains blank DATABASE_URL; `.env` is ignored and untracked.
- [x] `scripts/check_db.py` connects successfully.
- [x] Student reports Supabase settings confirmed. Browser inspection on November
  8 independently verified Enable Data API is off, with the message that no
  schemas can be queried through it. The Settings tab hides configuration while
  Data API is disabled, so automatic table exposure was not separately visible;
  its disabled state remains student-confirmed. No settings were changed.
- [ ] Confirm database password is saved in a password manager. Password storage
  was not inspected or requested during the browser check.
- [x] Five related tables have primary keys, foreign keys, appropriate types,
  constraints, and first_seen_at / last_updated_at audit columns.
- [x] `docs/schema.md` contains the matching ER diagram, row meanings, and a
  debated design rationale. The earlier design discussion is documented.
- [x] `ingest/load.py` loads 504 selected source records, parents first, with
  parameterized inserts and conflict handling. Current total: 570 works.
- [x] Audit rerun inserted zero rows; before/after comparison confirmed every
  stored row and audit timestamp unchanged.
- [x] Seven queries have plain-English comments, multiple JOINs, GROUP BY, and a
  publication-date filter. Live result interpretation is saved.
- [x] Query 5 records the student's surprise and corrects the maximum count
  from their initial interpretation of one to the actual result of two.
- [x] `docs/questions.md` preserves selected, deferred, and unanswerable questions.

## Submission preparation

- [x] AI review log prepared in `docs/ai_review_log.md`, including schema
  suggestions the student rejected or changed and why.
- [x] Agent checked 39 current nonignored files and 29 reachable local Git-history
  blobs for current credential matches and common credential patterns; no
  matches found. No secret `.env` files are tracked. This is a scoped scan,
  not a guarantee about remote-only history, screenshots, or video.
- [ ] Student final review of changes and PR review-log statements.
- [ ] Commit the Milestone 2 changes and create/prepare its pull request. At audit
  time, changes are uncommitted on the `milestone-1` branch; no Milestone 2 PR
  URL was verified.
- [ ] Record the 4–6 minute screencast: ER relationships, populated tables in
  Supabase, two queries with explanations, and duplicate-free loader rerun.
- [ ] Add the screencast link and completed AI review log to the PR and submit
  the Milestone 2 PR URL.

The live database and reruns were verified; a new clean-machine rebuild was not
performed during this audit. Do not claim that PR checklist item without doing
it. Initial schema creation on an empty database is documented separately in
`load_verification.md`. Automatic sync, proper update behavior, golden-question
evaluation, and the application UI belong to later milestones.
