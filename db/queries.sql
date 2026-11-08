-- Five initial reading-decision queries. Each statement runs independently.
-- Latest AI assessment = newest creation time, then highest assessment ID.
-- Ratings predict relevance, not verified quality or personal ratings.

-- Question 1: What are 10 articles rated 5/5 by AI with no recorded reading activity?
-- JOIN: works + assessments. Exclude both notes and recorded user reading status.
-- Missing activity means not recorded, not definitely unread.
WITH latest_ai AS (
    SELECT DISTINCT ON (work_id) work_id, value_rating
    FROM work_assessments WHERE assessed_by = 'ai'
    ORDER BY work_id, first_seen_at DESC, assessment_id DESC
)
SELECT w.title, w.publication_date, a.value_rating AS ai_value_rating
FROM works w
JOIN latest_ai a ON a.work_id = w.work_id
WHERE a.value_rating = 5
  AND NOT EXISTS (
      SELECT 1 FROM work_assessments u
      WHERE u.work_id = w.work_id AND u.assessed_by = 'user'
        AND u.reading_status IS NOT NULL
  )
  AND NOT EXISTS (SELECT 1 FROM reading_notes n WHERE n.work_id = w.work_id)
ORDER BY w.publication_date DESC NULLS LAST, w.work_id
LIMIT 10;

-- Question 2: How many distinct works are in each AI-assigned category?
-- GROUP BY: category. UNNEST expands the category array into individual rows.
-- A work can have multiple categories, so these counts are not additive.
WITH latest_ai AS (
    SELECT DISTINCT ON (work_id) work_id, categories
    FROM work_assessments WHERE assessed_by = 'ai'
    ORDER BY work_id, first_seen_at DESC, assessment_id DESC
)
SELECT c.category, count(DISTINCT a.work_id) AS work_count
FROM latest_ai a
CROSS JOIN LATERAL unnest(a.categories) AS c(category)
GROUP BY c.category
ORDER BY work_count DESC, c.category;

-- Question 3: What are the 10 highest-rated articles published in the last 90 days?
-- JOIN: works + assessments. TIME FILTER: publication_date.
-- Today plus the preceding 89 calendar dates; exclude future and unknown dates.
WITH latest_ai AS (
    SELECT DISTINCT ON (work_id) work_id, value_rating
    FROM work_assessments WHERE assessed_by = 'ai'
    ORDER BY work_id, first_seen_at DESC, assessment_id DESC
)
SELECT w.title, w.publication_date, a.value_rating AS ai_value_rating
FROM works w
JOIN latest_ai a ON a.work_id = w.work_id
WHERE w.publication_date BETWEEN CURRENT_DATE - 89 AND CURRENT_DATE
  AND a.value_rating IS NOT NULL
ORDER BY a.value_rating DESC, w.publication_date DESC, w.work_id
LIMIT 10;

-- Question 4: What articles connect to articles I have already written notes on?
-- JOINs: distinct noted works, connections, two works, and AI assessments.
-- Traverse either endpoint without reversing the meaning of the explanation.
-- One row per noted-work/connection pair, not per note. Show 10 highest-rated pairs.
WITH latest_ai AS (
    SELECT DISTINCT ON (work_id) work_id, value_rating
    FROM work_assessments WHERE assessed_by = 'ai'
    ORDER BY work_id, first_seen_at DESC, assessment_id DESC
), noted AS (
    SELECT DISTINCT work_id FROM reading_notes
    WHERE NULLIF(btrim(notes), '') IS NOT NULL
)
SELECT original.title AS article_with_my_notes,
       related.title AS connected_article,
       a.value_rating AS connected_ai_value_rating,
       c.connection_type, c.explanation
FROM noted n
JOIN works original ON original.work_id = n.work_id
JOIN work_connections c ON n.work_id IN (c.from_work_id, c.to_work_id)
JOIN works related ON related.work_id = CASE
    WHEN c.from_work_id = n.work_id THEN c.to_work_id ELSE c.from_work_id END
LEFT JOIN latest_ai a ON a.work_id = related.work_id
WHERE c.review_status <> 'rejected'
ORDER BY a.value_rating DESC NULLS LAST, related.publication_date DESC NULLS LAST,
         related.work_id, original.work_id, c.connection_id
LIMIT 10;

-- Question 5: Which authors have the most articles rated 5/5 by AI in my library?
-- JOIN: authorships + assessments. GROUP BY: author identity.
-- Prefer source author ID; fall back to normalized name when no ID exists.
-- Name-only grouping can conflate namesakes; counts do not establish reputation.
-- Observed 2026-11-08: the largest qualifying author count was only 2.
-- The student was surprised by the lack of repeated 5/5 recommendations for an
-- author and asked whether authors simply have few works in this collection.
-- Correction to their initial reading: the maximum was 2, not 1 (Pengcheng Chang
-- and Qiuhan Zhu). Questions 6 and 7 investigate total works regardless of rating.
WITH latest_ai AS (
    SELECT DISTINCT ON (work_id) work_id, value_rating
    FROM work_assessments WHERE assessed_by = 'ai'
    ORDER BY work_id, first_seen_at DESC, assessment_id DESC
)
SELECT min(au.author_name) AS author,
       count(DISTINCT au.work_id) AS articles_rated_5
FROM authorships au
JOIN latest_ai a ON a.work_id = au.work_id
WHERE a.value_rating = 5
GROUP BY coalesce(au.author_openalex_id, 'name:' || lower(btrim(au.author_name)))
ORDER BY articles_rated_5 DESC, author,
         coalesce(au.author_openalex_id, 'name:' || lower(btrim(au.author_name)))
LIMIT 10;

-- Question 6: How many authors have more than one work in this database,
-- and who are they, ordered from the most works to the fewest?
-- GROUP BY + HAVING: author identity with more than one distinct work.
-- The window count reports the total number of qualifying authors on each row.
-- No LIMIT: show every qualifying author, regardless of AI rating.
WITH author_counts AS (
    SELECT coalesce(author_openalex_id, 'name:' || lower(btrim(author_name))) AS author_key,
           min(author_name) AS author,
           count(DISTINCT work_id) AS work_count
    FROM authorships
    GROUP BY coalesce(author_openalex_id, 'name:' || lower(btrim(author_name)))
    HAVING count(DISTINCT work_id) > 1
)
SELECT author, work_count, count(*) OVER () AS authors_with_multiple_works
FROM author_counts
ORDER BY work_count DESC, author, author_key;

-- Question 7: What works belong to the author with the most works in this database?
-- JOINs: top authors + authorships + works + latest AI assessments.
-- Include ALL tied leaders rather than arbitrarily choosing one author.
-- Include unassessed works (NULL rating), and count each work once per author.
WITH author_counts AS (
    SELECT coalesce(author_openalex_id, 'name:' || lower(btrim(author_name))) AS author_key,
           min(author_name) AS author,
           count(DISTINCT work_id) AS work_count
    FROM authorships
    GROUP BY coalesce(author_openalex_id, 'name:' || lower(btrim(author_name)))
), top_authors AS (
    SELECT * FROM author_counts
    WHERE work_count = (SELECT max(work_count) FROM author_counts)
), author_works AS (
    SELECT DISTINCT coalesce(author_openalex_id, 'name:' || lower(btrim(author_name))) AS author_key,
           work_id
    FROM authorships
), latest_ai AS (
    SELECT DISTINCT ON (work_id) work_id, value_rating
    FROM work_assessments WHERE assessed_by = 'ai'
    ORDER BY work_id, first_seen_at DESC, assessment_id DESC
)
SELECT t.author, t.work_count AS author_total_works,
       w.work_id, w.title, w.publication_date, a.value_rating AS ai_value_rating
FROM top_authors t
JOIN author_works aw ON aw.author_key = t.author_key
JOIN works w ON w.work_id = aw.work_id
LEFT JOIN latest_ai a ON a.work_id = w.work_id
ORDER BY t.author, t.author_key, w.publication_date DESC NULLS LAST, w.work_id;
