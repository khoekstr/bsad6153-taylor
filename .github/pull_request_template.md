## What this pull request does

Milestone 2 turns my collected articles into a PostgreSQL reading library in
Supabase. It adds the five-table schema, ER diagram, repeatable data loader,
assessments and connections, and seven queries to help me explore what to read next.

## Checklist

- [ ] I read every change in this pull request before submitting it.
- [ ] No secrets anywhere: not in code, not in `.env.example`, not in screenshots, not in Git history.
- [ ] I ran it from a clean start, and it works on top of my previous milestone.
- [x] Documentation for this milestone is updated (`docs/`, README).
- [ ] Screencast link: Pending — I will add it after recording.

## AI review log

### Direct: what I asked the AI to do

**Schema:** I asked the AI to use the database design we had recently discussed,
not the original three-table example. I wanted the tables to fit my reading
library: articles, author information, assessments, my notes, and connections
between articles. I also asked for a diagram and explanations of the relationships.

**Loading and assessments:** I asked the AI to load the 504 records we had already
collected and make sure a second run would not create duplicates. Before running
queries, I wanted assessments and article connections added. Later, I supplied
additional articles from my interest exploration, the class cases, and my own notes.

**Queries:** I asked for query ideas based on my baseline log, with extra options
to choose from. I wanted these first queries to be straightforward and asked the
AI to identify which used JOINs, GROUP BY, and a time filter.

### Read: what I checked in its output

**Schema:** I asked where I could review data types, NOT NULL rules, and CHECK
constraints. I questioned the table structure and how assessments would be stored,
focusing on whether the design matched how I wanted to use the library.

**Loading and assessments:** I reviewed the first ten assessments and told the AI
to continue. I asked what the assessments would add, when they should happen, and
how suggested connections would work. I supplied my notes and asked that they be
attached to the corresponding articles.

I reviewed `ingest/load.py` and noted `load_dotenv` and `os.environ.get` reading
the database URL from my local environment instead of putting credentials in the
code. I also checked the `%s` placeholders with values passed separately to the
query, and `ON CONFLICT (openalex_id) DO NOTHING` to prevent duplicate source records.

**Queries:** I reviewed the proposed questions and `db/queries.sql`, checking for
the JOINs, GROUP BY, ORDER BY, and LIMIT clauses I had requested.

### Verify: the evidence that it works

**Schema:** I reviewed the schema document in both GitHub and Supabase.

**Database and loader:** I ran the database connection check and got a successful
connection. The AI created the tables and checked the schema and diagram against
the design. I asked it to rerun the load verification; it reported zero new rows
and no changes to existing records or timestamps. After the additional imports,
the database had 570 works, 1,520 author credits, 557 assessment rows, 18 notes,
and 140 connections. The AI also ran five connection-validation tests, which
passed. These automated checks are documented in `docs/load_verification.md`;
they are separate from the commands I ran myself.

**Queries:** The AI ran all seven queries. I ran the category-count query directly
in Supabase and saw the same result: Learning had the most works, with 252. That
was not surprising to me because I responded more passionately to education-related
articles during my interest exploration. The follow-up author queries found 50 authors
with more than one work, and included both authors tied for the most. I ran query 7 in Supabase and confirmed the same
two authors with three articles each.

### Decide: what I accepted, changed, or rejected, and why

Most of my design decisions were to keep the database simple and focused on what
I needed. These are the schema suggestions I challenged:

1. **Separate author profiles.** The AI suggested an additional author table
   because that information was available through OpenAlex. I did not need
   separate author profiles to decide what to read. We kept names, available
   OpenAlex IDs, and author order in `authorships`. Author information can repeat
   across articles, but I can still query which authors appear in my library.

2. **Separate category tables.** The AI wanted a table for category information
   and another linking categories to articles. I was less concerned about
   managing categories as separate records and asked to keep them as a column
   on assessments. We used a list of allowed categories so an article can have
   more than one. This is simpler, but changing the allowed list requires a
   database rule change, and we do not keep a separate category-assignment history.

3. **Separate tables for my assessments and the AI's.** I asked why both could
   not go in `work_assessments`, with a field identifying who made each one.
   We used `assessed_by`. I have one current assessment per article, while the
   AI can have multiple assessments to preserve its history. Fields that do not
   apply stay blank; the AI should not decide whether I read or favorited an article.

4. **Too many ratings.** Interest and usefulness were similar enough for my
   purpose that I did not need separate scores. I also questioned whether
   relevance needed another score. We combined interest and usefulness into
   one 1–5 `value_rating` and kept a written relevance explanation. Novelty
   stayed separate because something can interest me without being new to me.

5. **Wordy category names.** The suggested names were too long and the differences
   were not clear enough. I wanted simpler labels. We settled on Learning, Work,
   Information, Society, Technology, and Discovery, with short descriptions.
   They are broader labels, but articles can belong to multiple categories.

**Assessment scope:** I chose abstract-only assessments for the initial research
articles to avoid spending tokens on full papers. I chose this chat for now, with
the option to use an API later. For class cases, I asked the AI to use the case
brief summaries and include the success/failure connections already established
by the course. I did not need to approve every suggested connection. My personal
notes needed to remain my words, separate from AI assessments.

**Query choices:** I pushed back on vague wording like “most highly rated” and
made the threshold specifically 5/5. I limited reading shortlists to ten results,
suggested counting works by category for GROUP BY, and asked for connected works
to be sorted by value. I rejected more complicated questions, such as comparing
AI recommendations with my reactions, because I wanted to test simpler queries first.

**Surprise and follow-up:** I was surprised that no authors had more than one
article rated 5/5. I asked for two more queries:
how many authors had multiple articles regardless of rating, and which works
belonged to the author with the most articles. Those became queries 6 and 7.

Result clarification: that was my initial interpretation. The verified result
was two authors with two 5/5 articles each, rather than a maximum of one.
