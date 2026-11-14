-- Expose existing source metadata. Unknown dates remain NULL.
BEGIN;
SET LOCAL lock_timeout = '5s';
ALTER TABLE works
 ADD COLUMN cited_by_count bigint GENERATED ALWAYS AS (
   CASE WHEN source = 'openalex' AND jsonb_typeof(raw->'cited_by_count') = 'number'
     AND raw->>'cited_by_count' ~ '^[0-9]{1,18}$'
     THEN (raw->>'cited_by_count')::bigint END) STORED,
 ADD COLUMN  publication_name text GENERATED ALWAYS AS (
   CASE WHEN source = 'openalex' THEN nullif(btrim(raw#>>'{primary_location,source,display_name}'),'') END) STORED,
 ADD COLUMN  is_retracted boolean GENERATED ALWAYS AS (
   CASE WHEN source = 'openalex' AND jsonb_typeof(raw->'is_retracted') = 'boolean'
     THEN (raw->>'is_retracted')::boolean END) STORED,
 ADD COLUMN  metadata_checked_at timestamptz;
COMMIT;
