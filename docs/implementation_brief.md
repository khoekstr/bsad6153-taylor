# Milestone 2 implementation and AI review notes

## Subsequent assessment and connection completion

At the student's direction, the chat-authored abstract-only assessment pass now
contains 481 assessments (23 works lack usable abstracts). The student then
authorized AI-suggested work connections and clarified that no acceptance/rejection
step is required. The focused connection pass saved 60 links across 61 works,
covering all 46 highest-rated works. Suggestions are immediately usable as AI
interpretations. No personal reading notes or comments were fabricated.

The connection importer validates both abstracts and uses parameterized inserts
with a stable unique key. An additive migration added this key to the existing
five-table schema; the ER diagram was updated. Five offline validation tests passed.
Live verification matched the saved suggestions and confirmed a second load inserted
zero rows and changed no stored rows or timestamps. Details are in `connections.md`
and `load_verification.md`. These are agent-executed checks, not claims of student
code review or individual approval of every suggestion.

Updated November 7, 2026. Working evidence for the eventual pull request, not a claim
that the student completed code review. Agent-executed live verification is documented below.

## Part C completed

At the student's request, the agent created the five-table schema in the empty
Supabase public schema, loaded 504 works, 1,516 credits, and 10 approved abstract-only
AI assessments, then reran the load. The rerun inserted zero rows; all stored records
and audit timestamps were unchanged. See `load_verification.md` for results and the
screencast command. No notes or connections were invented.

Added a nullable unique assessment `import_key` to prevent duplicate batch imports
while preserving the ability to save later AI reassessments. Updated the diagram and
loader accordingly. All data values remain parameterized. Private approved assessment
data stays outside the public repository. The sections below preserve earlier design
and offline verification context; their live-setup TODOs are superseded by this result.

## Directed work and design decisions

The student reviewed the tables and directed an update to the final five-table design:
works, authorships, reading_notes, work_assessments, and work_connections.

- Keep works focused on source metadata, with local identity and audit dates.
- Keep author credits rather than independent author profiles.
- Allow multiple editable, dated notes per work.
- Combine interest/usefulness into value_rating, and remove relevance_rating.
- Combine personal and AI assessments in one table, distinguished by assessed_by.
  Personal value, favorite, current progress, and revisit intent belong to the single
  user assessment. AI rows retain predicted value, novelty, and written explanations.
- Keep one editable user assessment per work and multiple historical AI assessments.
  Latest AI is determined by creation timestamp and ID, not edit timestamp.
- Reject the separate categories and work_categories tables. Store multiple selected
  category names directly on assessments. User choices override AI suggestions;
  NULL means no override and an empty list means deliberately no categories.
- Drop selection_reason from works; original search provenance remains in manifests.
- Retain required audit names with Created and Last edited labels in the future UI.

## Five AI suggestions I challenged

Rough draft for the Decide section of my PR, based on our November 7 design discussion.

1. **Separate author profiles.** The AI suggested an `authors` table along with
   `authorships` to connect authors to articles. My main question was what to read
   next, so I did not see enough benefit in maintaining separate author profiles.
   We kept the author names, available OpenAlex IDs, and author order in
   `authorships`. That means author information can repeat across articles, but
   I can still query which authors appear in my library.

2. **Separate category tables.** I questioned why we needed both `categories`
   and `work_categories` when I just wanted to assign categories to an article.
   I did not need to track a separate history of category assignments. We kept
   a list of allowed categories on each assessment instead. An article can still
   have multiple categories, and my choices can take priority over the AI's.
   The trade-off is that changing the allowed category list requires changing
   the database rule rather than just adding a category record.

3. **Separate tables for my assessments and the AI's.** I asked why both could
   not go in `work_assessments`, with something identifying who made the
   assessment. We used `assessed_by` for that. I have one current assessment per
   article, while the AI can have multiple assessments so its history is kept.
   Some fields do not apply to both of us and stay blank. For example, the AI
   should not decide whether I have read an article or marked it as a favorite.

4. **Too many ratings.** I felt interest and usefulness were similar enough
   for my purpose that I did not need to score them separately. I also questioned
   whether relevance needed another numerical score. We combined interest and
   usefulness into one 1–5 `value_rating` and kept a written explanation of
   relevance. Novelty stayed separate because something can interest me without
   being new to me. The simpler rating means I cannot separately compare
   interest and usefulness later.

5. **Wordy category names.** Labels such as “Learning, Thinking & Creativity”
   and “AI Technology, Reliability & Safety” were too long, and the differences
   were not clear enough to me. I wanted simpler labels. We settled on Learning,
   Work, Information, Society, Technology, and Discovery, with short descriptions
   explaining each one. These broader labels are less specific, but an article
   can belong to more than one category.

## Implementation

Updated SQL, the typed ER diagram, dictionary, loader, quality-check field mappings,
and usage documentation. SQL constraints distinguish user and AI rows; a partial
unique index limits user assessments to one per work. Upload metadata is nullable
except for title, source, and the file reference. RLS remains enabled on all tables.
The importer writes only works and credits, using parameters and conflict-safe inserts.

## Verification and remaining evidence

Local checks completed after this revision:

- Loader dry run: 504 works and 1,516 usable credits, matching the previous baseline.
- Quality-report regression: every generated measurement matches the saved JSON.
- Captured loader calls: all 2,020 calls bind the expected number of parameters;
  open-access/PDF/source URL/raw fields align with source payloads; writes target
  works and author credits only. This uses a capture stub, not a database server.
- Python compilation and schema/diagram field consistency checks passed.
- Git whitespace check passed.

These checks do not demonstrate PostgreSQL constraint execution or duplicate-free live
loads. No owner connection or secrets were used for offline validation.

The student still needs to read the changes, configure the Session pooler, apply the
schema to a NEW database, run the loader twice, and record live counts and permission
checks. Existing deployed drafts require a separately reviewed migration: this file
contains no migration and no existing database was altered.

Business queries, genuine assessment/note content, result interpretation, the student's
surprise finding, and screencast remain outstanding. UI authentication, category
fallback, user edits, and AI generation are future application work. Do not invent
personal review actions or data to complete the assignment log.
