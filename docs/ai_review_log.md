# Milestone 2 AI review log

Draft for me to revise before submitting. This reflects our conversation so far;
I still need to describe any additional code review and checks I do myself.

## Schema and documentation

**Direct:** I asked the AI to use the database design we had recently discussed,
not the original three-table example. I wanted the tables to fit my
reading library, with articles, author information, assessments, my notes, and
connections between articles. I also asked for a diagram and an explanation of
the relationships.

**Read:** I asked where I could review the data types, NOT NULL rules, and CHECK
constraints. I questioned the table structure and how the assessments would be
stored. I focused on whether the design matched how I wanted to use the library.

**Verify:** I ran the database connection check and got a successful connection.
The AI created the tables and checked the schema and diagram against the design.
Those were checks the AI performed, not commands I personally ran.

**Decide:** Most of my decisions were to force the AI to keep the database simple.  The AI had suggested an additional table for author information (since it was available via open alex), but I stated I did not need that.  Also, AI wanted to add two tables for categories (one with id, category and description, and another to track how they were used). I was less concerned about the assigned category and said to delete them and just put category as a column in the assessment table. I also did not
need separate interest and usefulness ratings, so we combined those into one
value rating. I wanted my assessments and the AI's assessments in the same table,
with a field showing who made each assessment. This kept the design simpler while
still keeping my opinions separate from the AI's suggestions.

## Loading, assessments, connections, and my notes

**Direct:** I asked the AI to load the 504 records we had already collected and
make sure running the load again would not create duplicates. Before running
queries, I wanted the AI assessments and article connections added too. Later,
I provided additional articles I read when determining my interest as well as the class cases and my own notes to include in the library.

**Read:** I asked what the assessments would add and when they should happen. I
also asked how the connections between articles would work and what “suggested”
meant. I reviewed the first ten assessments and told the AI to continue. I supplied
my personal notes and asked that they be attached to the corresponding articles.  I reviewed load.py and noted load_dotenv and os.environ.get to get the database url and read the password without putting the info in the code. I also noted the %s as values in the query to avoid SQL injections as well as the literal code ON CONFLICT (openalex_id) DO NOTHING to prevent duplicate records.


**Verify:** I asked the AI to rerun the load verification. It reported zero new
rows on the rerun and no changes to existing records or timestamps. After the
additional articles and notes, the database had 570 works, 1,520 author credits,
557 assessment rows, 18 notes, and 140 connections. The AI also ran five connection
validation tests, which passed. The details are saved in `load_verification.md`.

**Decide:** For the initial research articles, I chose assessments based only on
the abstracts because I did not want to spend the tokens on full papers. I chose
to do the assessments in this chat for now, with the option to use an API later.
For the class cases, I asked the AI to use the summaries from the case brief
instructions. I also clarified that I did not need to approve every suggested
connection. I wanted the suggestions available without another review step, although i did instruct AI to make the connections already established by the case briefs (success vs. failure).
My personal notes needed to remain my words, separate from AI assessments.

## Queries and what I learned

**Direct:** I asked for query ideas based on my baseline log, with a few extra
options to choose from. I wanted these first queries to be straightforward. I
asked the AI to identify which queries used JOINs, GROUP BY, and a time filter.

**Read:** I reviewed the proposed questions and pushed back on vague wording like
“most highly rated.” We made that specifically 5/5. I was concerned that a reading
list would be too long, so we limited it to ten results. I liked the recent-article
and author questions, and suggested that GROUP BY could simply count works by
category. I also asked for connected articles to be sorted by value rating. Lastly, I reviewed the queries.sql document to inspect the SQL code used to ensure it had the JOINs, GROUP BY, ORDER BY, and LIMITS I specificially asked for.

**Verify:** The AI ran five queries and reported the results. The author
follow-ups found 50 authors with more than one work in this database. Two authors
tied for the most, with three works each. The query listed both authors rather
than choosing one arbitrarily. I ran the groupby query directly in supabase and noted the same results AI did (of the works in the database, most are categorized as Learning).  This isn't surprising since in my discovery of interests phase I responded more passionately to education related articles. I also completed the added 7th query and noted the same two authors with 3 articles each in the database.

**Decide:** I rejected some of the more complicated questions for now, such as
comparing AI recommendations with my reactions. Those may be useful later, but
this week I wanted to start by testing simpler queries. I was surprised that no authors had more than one article rated 5/5. So I asked AI to add 2 more queries... one to see how many others had more than one article (regardless of rating) and for the author with the most number of articles, give me the titles and publication dates for those articles.
## Before I submit
