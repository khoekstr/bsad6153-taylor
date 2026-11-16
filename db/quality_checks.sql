-- Part E. Run as app_reader in a REPEATABLE READ, READ ONLY transaction.
-- SET LOCAL TIME ZONE 'America/Chicago'; record transaction_timestamp() with results.
-- QC01: row counts (the seven application tables).
SELECT 'works' AS table_name, count(*) AS rows FROM works
UNION ALL SELECT 'authorships',count(*) FROM authorships
UNION ALL SELECT 'reading_notes',count(*) FROM reading_notes
UNION ALL SELECT 'work_assessments',count(*) FROM work_assessments
UNION ALL SELECT 'work_connections',count(*) FROM work_connections
UNION ALL SELECT 'sync_state',count(*) FROM sync_state
UNION ALL SELECT 'sync_runs',count(*) FROM sync_runs;

-- QC02: important missing fields; blank text counts as missing.
SELECT field, count(*) AS denominator, count(*) FILTER(WHERE missing) AS missing,
 round(100.0*count(*) FILTER(WHERE missing)/nullif(count(*),0),2) AS missing_pct
FROM works CROSS JOIN LATERAL (VALUES
 ('title',nullif(btrim(title),'') IS NULL),('abstract',nullif(btrim(abstract),'') IS NULL),
 ('publication_date',publication_date IS NULL),('doi',nullif(btrim(doi),'') IS NULL),
 ('language',nullif(btrim(language),'') IS NULL),('primary_topic',nullif(btrim(openalex_topic),'') IS NULL),
 ('pdf_url',nullif(btrim(pdf_url),'') IS NULL),('cited_by_count',cited_by_count IS NULL),
 ('publication_name',nullif(btrim(publication_name),'') IS NULL),
 ('is_retracted',is_retracted IS NULL),('metadata_checked_at',metadata_checked_at IS NULL)
) AS f(field,missing) GROUP BY field ORDER BY field;

-- QC03: assessment missingness; no rating is not a negative rating.
SELECT count(*) AS assessments,
 count(*) FILTER(WHERE value_rating IS NULL) AS missing_value_rating,
 count(*) FILTER(WHERE categories IS NULL OR cardinality(categories)=0) AS no_categories,
 (SELECT count(*) FROM works w WHERE NOT EXISTS
   (SELECT 1 FROM work_assessments a WHERE a.work_id=w.work_id)) AS unassessed_works
FROM work_assessments;

-- QC04: duplicate groups (not counts of excess rows); title matches need review.
SELECT 'openalex_id' AS check_name,count(*) AS duplicate_groups FROM
 (SELECT openalex_id FROM works WHERE openalex_id IS NOT NULL GROUP BY openalex_id HAVING count(*)>1) d
UNION ALL SELECT 'normalized_doi',count(*) FROM
 (SELECT regexp_replace(lower(btrim(doi)),'^(https?://(dx\.)?doi\.org/|doi:\s*)','') AS k
 FROM works WHERE nullif(btrim(doi),'') IS NOT NULL GROUP BY k HAVING count(*)>1) d
UNION ALL SELECT 'normalized_title',count(*) FROM
 (SELECT regexp_replace(lower(btrim(title)),'\s+',' ','g') AS k FROM works GROUP BY k HAVING count(*)>1) d
UNION ALL SELECT 'work_author_id',count(*) FROM
 (SELECT work_id,author_openalex_id FROM authorships WHERE author_openalex_id IS NOT NULL
 GROUP BY work_id,author_openalex_id HAVING count(*)>1) d;

-- QC05: invalid or inconsistent values; future dates are review flags, not automatic errors.
SELECT 'future_publication_date' AS check_name,count(*) AS flagged FROM works WHERE publication_date>CURRENT_DATE
UNION ALL SELECT 'date_year_disagreement',count(*) FROM works WHERE extract(year FROM publication_date)<>publication_year
UNION ALL SELECT 'negative_citations',count(*) FROM works WHERE cited_by_count<0
UNION ALL SELECT 'invalid_value_rating',count(*) FROM work_assessments WHERE value_rating NOT BETWEEN 1 AND 5
UNION ALL SELECT 'invalid_categories',count(*) FROM work_assessments
 WHERE NOT(categories <@ ARRAY['Learning','Work','Information','Society','Technology','Discovery']::text[]) OR array_position(categories,NULL) IS NOT NULL
UNION ALL SELECT 'nonpositive_reading_minutes',count(*) FROM work_assessments WHERE estimated_reading_minutes<=0
UNION ALL SELECT 'invalid_author_order',count(*) FROM authorships WHERE author_order<=0
UNION ALL SELECT 'self_connection',count(*) FROM work_connections WHERE from_work_id=to_work_id
UNION ALL SELECT 'work_update_before_first_seen',count(*) FROM works WHERE last_updated_at<first_seen_at
UNION ALL SELECT 'sync_finish_before_start',count(*) FROM sync_runs WHERE finished_at<started_at
UNION ALL SELECT 'negative_sync_counts',count(*) FROM sync_runs WHERE least(records_fetched,records_inserted,records_updated)<0;

-- QC06: orphans and optional author coverage.
SELECT 'authorship_orphans' AS check_name,count(*) AS flagged FROM authorships c LEFT JOIN works p USING(work_id) WHERE p.work_id IS NULL
UNION ALL SELECT 'note_orphans',count(*) FROM reading_notes c LEFT JOIN works p USING(work_id) WHERE p.work_id IS NULL
UNION ALL SELECT 'assessment_orphans',count(*) FROM work_assessments c LEFT JOIN works p USING(work_id) WHERE p.work_id IS NULL
UNION ALL SELECT 'connection_from_orphans',count(*) FROM work_connections c LEFT JOIN works p ON p.work_id=c.from_work_id WHERE p.work_id IS NULL
UNION ALL SELECT 'connection_to_orphans',count(*) FROM work_connections c LEFT JOIN works p ON p.work_id=c.to_work_id WHERE p.work_id IS NULL
UNION ALL SELECT 'works_without_authors',count(*) FROM works p WHERE NOT EXISTS(SELECT 1 FROM authorships c WHERE c.work_id=p.work_id);

-- QC07: fairness coverage, including unknowns; never infer author demographics.
SELECT coalesce(nullif(btrim(language),''),'unknown') AS language,
 coalesce(is_open_access::text,'unknown') AS open_access,count(*) AS works,
 count(*) FILTER(WHERE nullif(btrim(abstract),'') IS NULL) AS missing_abstracts
FROM works GROUP BY 1,2 ORDER BY 1,2;

-- QC08: date coverage and source composition.
SELECT source,count(*) AS works,min(publication_year) AS earliest_year,max(publication_year) AS latest_year,
 count(*) FILTER(WHERE publication_year IS NULL) AS unknown_year,
 count(*) FILTER(WHERE publication_year>=extract(year FROM CURRENT_DATE)-1) AS current_or_previous_year
FROM works GROUP BY source ORDER BY source;

-- QC09: actual foreign-key definitions, including deletion behavior.
SELECT conrelid::regclass::text AS child_table,conname,pg_get_constraintdef(oid) AS definition
FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace ORDER BY 1,2;
