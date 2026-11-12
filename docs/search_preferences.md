# Search preferences

Agreed November 11, 2026. Edit `ingest/search_preferences.json`; the sync reads it
on each run. This document explains the settings. General topics only are sent
to OpenAlex. Personal notes are never read by the fetcher or transmitted to it.
When we discuss new notes or interests, update the topic file to reflect that
feedback; automatic extraction from notes is not implemented in Part B.

## Current priorities

1. AI and parenting (from the example interest discussed in chat).
2. AI pilot evaluation, costs, and benefits (from the recorded question list).
3. Generative AI, critical thinking, and learning.
4. AI and human agency.

Smaller priority numbers run first. Within each topic's fetched candidates,
newest publication date comes first, then source ID for reproducible ties.
These are search matches, not a model's relevance or quality assessment.
The initial general topics are editable, not inferred private personal facts.

## Controls

- `max_additions`: 1 through 5; default 5. Code rejects values above 5.
- `topics[].enabled`: set false to stop searching that topic.
- `topics[].match_terms`: when paused, these phrases also exclude matching
  titles/abstracts/topic labels from other searches and the fallback.
- `excluded_terms`: phrases to exclude everywhere, regardless of active topics.
- `topics[].priority`: lower numbers first. Change `query` to refine a search.
- `max_pages_per_topic`: candidate pages per topic; default 2, at most 5.
- `max_requests`: includes retries, default 40. Hitting the cap fails and rolls back.
- `sync_filter_access`: `free` by default. Use `paid` only if an existing OpenAlex
  plan supports updated-date filters; this setting does not purchase a plan.

Paused-topic/excluded-term matching ignores case and punctuation but is lexical,
not semantic: add synonyms yourself. Existing library records are never removed
because a topic is paused. Daily runs leave all existing article metadata alone.
An early priority can fill all five slots; no equal-topic quota is imposed.

## Fixed rules

New records must be English and open access with a known, nonfuture publication
date. No category or publication-year cutoff. Exclude existing OpenAlex IDs,
normalized DOIs, and exact normalized titles, including matches to manual works.
Title matching is conservative and may omit distinct versions with the same title.
No existing records are merged or deleted by this duplicate check.

Aim for five relevant additions. If none qualify, search all categories and take
one eligible new paper. Outages, missing dates, exclusions, or the bounded search
can still result in zero; the pipeline never fabricates a paper to meet a minimum.
The page bound means "newest" is among eligible candidates inspected, not a claim
of exhaustive search of the entire OpenAlex corpus.

One successful discovery pass is allowed per UTC calendar day. Same-day reruns
make no API requests or data edits, even if preferences change. Failed and dry
runs do not consume the day. Reusing the preferences requires no new reading.

The agreed four-day schedule is not installed by Part B. New papers remain
assessment-pending until a separate AI assessment step is configured. Part B
does not call an AI provider or spend any of the $20 assessment budget.

Existing articles are refreshed only through an explicit one-article maintenance
command with a stated reason. There is no automatic metadata review.

Part D configures a four-day scheduled trial for November 13-16, 2026; see the
repository README for time, stop conditions, secrets, and manual-run instructions.
