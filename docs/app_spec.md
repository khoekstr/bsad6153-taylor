# AI Research Discovery — Milestone 4 App Spec

## Audience and purpose

This Streamlit research library is primarily for me, an Applied AI graduate student deciding twice weekly what to read next. Baseline searches took 1–30 minutes, with low confidence in relevance, credibility, and novelty to me. Public visitors can browse recommendations tailored to my interests, with clear sources and limitations. AI scores estimate personal interest. My notes, reading history, and personal ratings remain private.

## Questions and views

1. **What recent research might be worth reading, and why?** Discover shows up to five papers published within 30 calendar days, ranked by their latest saved AI interest scores. Distinguish publication date from date added. Missing scores mean unknown.
2. **What else might interest me?** Explore includes older material and unfamiliar subjects, with keyword search and filters for topic, publication date range, and minimum AI interest score. Controls change SQL through bound parameters. Unassessed papers remain accessible without score filtering.
3. **How current are these results?** A top banner reads `sync_runs` for the last successful committed sync and elapsed time. Target ongoing updates are Monday and Thursday. Warn after four days without success, or when success cannot be confirmed. Exclude previews from freshness calculations.

Adapt Readwise's shortlist and Zotero's source-centered layout. Article cards show title, date, topic, source/DOI link, score, recommendation explanation, and saved AI summary. Offer an expandable original abstract, also the fallback when summaries are missing. Label assessment basis and unavailable information.

Build on `db/queries.sql` and golden questions Q02, Q05, and Q12, adapting recency to 30 days. Never fabricate data.

## Connection and privacy

The instructor approved authenticated note-taking for Milestone 4. Visitors browse personalized recommendations with a read-only database login through `APP_DATABASE_URL`. The website uses a dedicated public reader with access to displayable columns. The older `app_reader` also reads private data for local course checks.

Only my verified Google account can open My notes or save a notebook entry. From a paper I can copy a passage, record its location, capture my own words and optionally mark reading progress. My notebook includes earlier entries and links back to their papers. The server checks my identity on every private read and save and uses a separate restricted notebook login. All inputs use bound SQL parameters. Keep secrets, database errors, private activity and restricted sources off the public site.

## Definition of done

- Discover and Explore answer the research questions above. Display source links, assessment limitations, friendly empty and error states, and the student-project About section.
- Cache public query results for 15 minutes and document the tradeoff. Read private notes directly on each request.
- Preserve my wording. A successful save adds one entry to the selected paper. A failed save keeps my draft for retry. Notes and quotations remain separate.
- Saving records only my entry. Reassess recommendations separately, only when I explicitly ask. No AI API calls from the website.
- Verify public counts against direct SQL, public write and private-read denial, owner-only notebook access, persistence after sign-out/sign-in, and duplicate-save protection.
- Deploy on Render over HTTPS with server-side secrets. Document the website URL, local setup, and free-tier wake-up delay.
