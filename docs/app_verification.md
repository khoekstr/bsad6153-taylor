# Public library count verification

Checked 2026-11-23 19:42 UTC as `library_web_reader`. Read the signed-out Discover caption with Streamlit AppTest and ran the SQL below directly against Supabase in a separate read-only connection.

| Number | App | Direct SQL | Result |
|---|---:|---:|---|
| Public papers | 591 | 591 | Match |
| Published in 30 days | 21 | 21 | Match |
| Awaiting an AI interest score | 41 | 41 | Match |

The recent window includes today and the preceding 29 UTC dates. The assessment check reads the newest AI assessment for each eligible paper.

```sql
SELECT count(*) AS total,
       count(*) FILTER (WHERE w.publication_date BETWEEN
           (now() AT TIME ZONE 'UTC')::date - 29 AND
           (now() AT TIME ZONE 'UTC')::date) AS recent,
       count(*) FILTER (WHERE (
           SELECT a.value_rating FROM public.work_assessments a
           WHERE a.work_id = w.work_id AND a.assessed_by = 'ai'
           ORDER BY a.first_seen_at DESC, a.assessment_id DESC LIMIT 1
       ) IS NULL) AS awaiting
FROM public.works w
WHERE w.source = 'openalex'
   OR (w.source = 'upload' AND w.source_url ~* '^https?://');
```
