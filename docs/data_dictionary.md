# Data dictionary: personal AI reading library

Prepared October 29, 2026. This document describes downloaded OpenAlex metadata;
the PostgreSQL database and personal reading features have not been built yet.
Examples and observations below come from the local collection, not invented records.

## 1. Source and collection scope

- **API:** OpenAlex; base URL: `https://api.openalex.org`.
- **Endpoints used:** `GET /works` for title searches and topic searches;
  `GET /authors` for separate records linked by the works' author IDs.
- **Parameters:** `search`, `filter`, `per_page`, and `cursor`. General searches
  use `type:article,language:en,is_oa:true`; requested papers are handled separately.
  Reviewed `openalex_id` filters are now configured for future required-paper lookups.
- **Authentication:** `Authorization: Bearer <key>`. The script reads
  `OPENALEX_API_KEY` from local `.env`; `.env.example` contains only the blank name.
  Keys are not included in request URLs, raw records, or this document.
- **Documentation:** [API reference](https://help.openalex.org/api/),
  [authentication](https://help.openalex.org/api/authentication/),
  [pagination](https://help.openalex.org/api/paging/),
  [filters](https://help.openalex.org/api/filtering/),
  [work fields](https://help.openalex.org/data/works/attributes/), and
  [common entity fields](https://help.openalex.org/data/common-attributes/).
- **Terms:** [OpenAlex Terms of Service](https://openalex.org/OpenAlex_termsofservice.pdf)
  (revised October 2, 2026); [data licensing statement](https://help.openalex.org/data/how-its-built/)
  and [CC0 explanation](https://creativecommons.org/publicdomain/zero/1.0/).

The first successful run, `20261029T155716Z_d357540f`, selected **500 unique works**
and retrieved **1,451 distinct author records**, using 51 API requests. It saved
about 39.55 MB in 54 files before the subsequent review files were added.
Nine selected works had empty/missing authorships; all author IDs requested in that
run were returned. This does not prove the authorship metadata is complete or correct.

The later reviewed selection contains **504 works**, including all 12 requested
research papers. Four required works were added from already-downloaded search results;
two other previously unresolved papers were already in the selected 500. The original
run summary remains unchanged. Separate author retrieval has not been repeated for the
four additions, so the 1,451 count describes the original run, not a verified complete
author set for all 504 works.

Evidence, relative to the repository root:

- `data/raw/20261029T155716Z_d357540f/summary.json`: original counts and warnings.
- `data/raw/20261029T155716Z_d357540f/reviewed_selection.json`: reviewed IDs and provenance.
- `data/raw/20261029T155716Z_d357540f/reading_list.csv`: readable candidate list.
- `data/sample/openalex_sample.json`: one unmodified work and author excerpt for review.
- `ingest/selection.json`: six search categories, queries, and required-paper IDs.

Raw downloads are ignored by Git. One JSON response can contain many records;
one JSON file is not one article. Responses also contain unselected search candidates.
No full-text articles, PDFs, videos, or personal reading notes were downloaded.

## 2. What one record means

**Work:** One record describes one scholarly work as represented by OpenAlex,
such as an article; it contains bibliographic information and links rather than the
full article. A work record is a reading candidate, not evidence that the user read it.

**Author:** One record is OpenAlex's profile for a person credited with scholarly
work. Identity matching is automated and can incorrectly combine or split people;
the profile is not a verified personal account.

**Authorship:** One nested entry connects an author to a particular work, with
position and affiliation information. We plan to turn these into a linking table;
they were obtained inside works, not from a third endpoint.

## 3. Important fields

The table lists **20 fields**. Types describe the JSON, not final SQL columns.
`[]` means an array; dotted paths identify nested fields. “Missing” includes absent
keys, null values, and empty arrays where applicable. Examples are observed values;
short objects are explicitly excerpts. These are snapshots, so counts can change.

| Resource / field | JSON type | Observed example | Meaning | Can be missing? |
|---|---|---|---|---|
| Work `id` | string | `https://openalex.org/W4400578758` | Source identifier for the work. | Required by this importer; invalid records skipped. |
| Work `display_name` | string/null | `Generative AI enhances individual creativity but reduces the collective diversity of novel content` | Title. | Yes upstream; blank titles skipped. |
| Work `doi` | string/null | `https://doi.org/10.1126/sciadv.adn5290` | External publication identifier. | Yes; not every work has a DOI. |
| Work `type` | string | `article` | OpenAlex's resource classification. | Expected; validate when loading. |
| Work `language` | string/null | `en` | Detected metadata language. | Yes; does not guarantee full-text language. |
| Work `publication_date` | string/null | `2024-07-12` | Publication date. | Yes; 2 missing in the original 500. |
| Work `publication_year` | integer/null | `2024` | Publication year. | Allow unknown; do not invent a date. |
| Work `abstract_inverted_index` | object/null | Excerpt: `{"Creativity":[0],"is":[1,142]}` | Words mapped to positions. | Yes; 16 missing/empty in the original 500. |
| Work `authorships[].author.id` | string/null | `https://openalex.org/A5011170431` | Link to an author record. | Yes; 9 works lacked authorships. |
| Work `authorships[].author_position` | string/null | `first` | Author's position on this work. | Allow unknown. |
| Work `open_access.is_oa` | boolean | `true` | OpenAlex reports an open copy. | Allow unknown on manual/other records. |
| Work `best_oa_location.pdf_url` | string/null | `https://www.science.org/doi/pdf/10.1126/sciadv.adn5290?download=true` | Link to an open PDF. | Yes; URL accessibility not tested. |
| Work `best_oa_location.license` | string/null | `cc-by` | Reported license for that copy. | Yes; unknown is not permission. |
| Work `biblio` | object with string/null members | Excerpt: `{"first_page":"eadn5290","last_page":"eadn5290"}` | Citation/page labels. | Members can be missing or nonnumeric. |
| Work `primary_topic.display_name` | string/null | `Creativity in Education and Neuroscience` | Provider-assigned subject label. | Allow missing; not our search category. |
| Work `updated_date` | string | `2026-10-29T09:56:32.521200` | Provider's last-change timestamp. | Preserve raw value; handle absent/invalid values. |
| Author `id` | string | `https://openalex.org/A5000934027` | Source identifier for the profile. | Required by this importer. |
| Author `display_name` | string | `Lee A. Fleisher` | Profile name. | Blank/missing names skipped by importer. |
| Author `orcid` | string/null | `https://orcid.org/0000-0003-2899-2294` | Linked researcher identifier. | Yes; never identify people by name alone. |
| Author `works_count` | integer | `748` | Works associated with this profile. | Expected; permit unknown on incomplete records. |

These interpretations use the official [work dictionary](https://help.openalex.org/data/works/attributes/)
and [common attributes](https://help.openalex.org/data/common-attributes/), checked
against our JSON. An open-access flag, topic, publication count, or citation count
is not a credibility rating.

## 4. Identifiers and relationships

Keep each OpenAlex `id` as a unique source identifier: works start with `W`, authors
with `A`. The future database will also generate its own bigint identity primary keys
(`work_id`, `author_id`), retaining unique provider IDs so repeated imports update
existing rows. Manual items can then have local IDs without pretending to be OpenAlex works.

`work.authorships[].author.id` refers to `author.id`. Works and authors have a
many-to-many relationship: one work can have many authors, and an author can write
many works. A planned `authorships` table will hold foreign keys to both tables;
affiliations belong to the authorship context rather than being assumed permanent.

DOIs provide a second matching signal. Titles are not unique: versions, corrections,
and different publications can share wording. Do not merge solely by title or name.
OpenAlex IDs can be merged upstream; retain a mapping to a surviving ID and review
unexpected replacements rather than silently deleting local notes.

Our six category labels record the search that selected an item. They are provisional
local labels, distinct from OpenAlex topics. Required papers are marked `required`
in the reviewed selection; that is a selection reason, not a seventh subject category.

## 5. Update behavior

OpenAlex continuously ingests sources and its catalog evolves daily; older records
can gain corrected metadata, links, abstracts, citations, or different identity matches.
The source publication date is different from when OpenAlex discovers a work and
from when our library first collects it. [How OpenAlex is built](https://help.openalex.org/data/how-its-built/)

**Current behavior:** each fetch starts searches at cursor `*`, uses next cursors
within the run, and deduplicates within that run. It does not resume earlier runs,
compare against a database, or implement scheduled updates.

**Planned free-tier weekly sync:** repeat recent-publication searches with an overlap,
insert unseen IDs, and refresh stored IDs in batches. Compare normalized record hashes
and provider timestamps where available; retain local `first_seen_at` and
`last_updated_at` separately. Periodically repeat broader searches to discover older
works newly indexed by OpenAlex; this approach cannot guarantee complete detection.

The official `from_created_date` and `from_updated_date` filters require a paid plan,
so they are not assumed available. Merges/deletions also need reconciliation; a failed
request alone is not evidence to delete a record. [Official sync documentation](https://help.openalex.org/access/sync/)

Store audit times as timezone-aware UTC timestamps. The observed provider timestamp
has no explicit offset; confirm its timezone convention before conversion and keep
the original string. A changed record is not necessarily a newly published article.

## 6. Observed surprises and consequences

These are findings from the download/review, not claims about what the student
personally expected. The student should review and explain the findings in their own words.

1. **Missing information despite accessible articles:** among the original 500,
   16 lacked abstracts, 9 lacked authorships, and 2 lacked publication dates.
   Summaries must state their evidence basis; missing values must not become invented facts.
2. **Page labels are not always page numbers:** the creativity paper uses `eadn5290`
   in both page fields. Subtracting these fields would not give a valid reading length.
3. **Exact titles can be ambiguous:** the downloaded searches returned multiple
   `Generative AI at Work` records, including journal and working-paper versions.
   Four duplicate work encounters were also skipped during the initial selection.
   Use IDs and version evidence rather than title-only deduplication.
4. **Shortened titles caused missed automatic matches:** the tutoring, deepfakes,
   and guardrails titles included subtitles in OpenAlex. Reviewed IDs now resolve
   those requested papers without relying on identical title strings.
5. **Dates may differ from a supplied citation:** the QJE version of `Generative AI
   at Work` is indexed with year 2024, whereas the supplied journal citation used
   2025. Preserve the source value and verify online/issue dates before citing it;
   do not silently overwrite it to match the supplied citation.
6. **Abstracts arrive as word-position mappings:** the creativity record starts with
   `Creativity: [0]`, not a ready-to-display paragraph. Reconstruction and missing-data
   handling are required before treating this field as readable text.

## 7. Data-use ethics check

**What do the terms allow and forbid: storage, display, commercial use, attribution?**
OpenAlex's explicit CC0 metadata statement supports copying, storing, displaying,
and commercial reuse without a copyright attribution condition (we will still credit
OpenAlex and link sources), but the service terms contain broad restrictions on
unauthorized reuse; this apparent tension needs clarification before public republication.
CC0 does not grant rights to third-party articles, images, trademarks, or private information:
check the particular copy's license before redistributing text/PDFs and follow service
access limits. [Data statement](https://help.openalex.org/data/how-its-built/),
[CC0](https://creativecommons.org/publicdomain/zero/1.0/),
[service terms, “Your Rights to Use the Service”](https://openalex.org/OpenAlex_termsofservice.pdf)

**Does the data describe identifiable people, and did they expect this use?**
Yes: names, ORCIDs, affiliations, and publication histories identify real researchers;
scholarly discovery is consistent with their public publication context, but we cannot
assume individual consent to every aggregation or automated judgment.
Use the records for finding research, not sensitive profiling or unsupported author rankings.

**What is the worst realistic harm if the copy leaked or were misread?**
Misidentified authors or unsupported credibility judgments could damage reputations or
mislead a reader; public metadata alone has lower confidentiality risk than the future
personal layer. A leak of that layer could expose private interests, criticism, unfinished
research ideas, and notes, so it must be kept separate from public catalog access.

**Who should read or change these records?**
The intended public catalog reader may read approved bibliographic fields, while only
the trusted ingestion process should update provider records; the owner alone should
access or edit private notes, ratings, and history through authenticated, limited permissions.
The course starts with a read-only website database role, so personal-note writes need
an explicitly scoped later design consistent with the course rules; these controls are
planned, not yet implemented.

## 8. Future personal fields are not API facts

Reading status, usefulness/interest ratings, notes, quotations, pins, and collections
will be private user-generated records linked to works. Relevance, novelty, credibility
assessments, and plain-language summaries will be separately labeled AI outputs with
an explanation, evidence basis, and timestamp; none exists in the imported metadata.
Novelty requires actual reading history, and discussing a paper does not establish that
it was fully read. The two personal essays remain planned manual additions.
