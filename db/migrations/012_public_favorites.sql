-- Run as the database administrator after migrations 010 and 011.
BEGIN;

ALTER TABLE public.work_assessments ADD COLUMN IF NOT EXISTS starred_at timestamptz;

CREATE OR REPLACE FUNCTION public.track_favorite_time() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NEW.is_favorite IS NOT TRUE THEN
        NEW.starred_at := NULL;
    ELSIF TG_OP = 'INSERT' THEN
        NEW.starred_at := statement_timestamp();
    ELSIF OLD.is_favorite IS DISTINCT FROM TRUE THEN
        NEW.starred_at := statement_timestamp();
    ELSE
        NEW.starred_at := OLD.starred_at;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS track_favorite_time ON public.work_assessments;
CREATE TRIGGER track_favorite_time BEFORE INSERT OR UPDATE OF is_favorite
    ON public.work_assessments FOR EACH ROW EXECUTE FUNCTION public.track_favorite_time();

-- Project only eligible favorite IDs and their display order to the public reader.
CREATE SCHEMA IF NOT EXISTS library_display;
REVOKE ALL ON SCHEMA library_display FROM PUBLIC;
GRANT USAGE ON SCHEMA library_display TO library_web_reader;
CREATE OR REPLACE VIEW library_display.favorite_reads WITH (security_barrier = true) AS
SELECT w.work_id, row_number() OVER (
    ORDER BY f.starred_at DESC NULLS LAST, w.publication_date DESC NULLS LAST, w.work_id
) AS position
FROM public.work_assessments f
JOIN public.works w ON w.work_id = f.work_id
JOIN LATERAL (
    SELECT a.summary FROM public.work_assessments a
    WHERE a.work_id = w.work_id AND a.assessed_by = 'ai'
    ORDER BY a.first_seen_at DESC, a.assessment_id DESC LIMIT 1
) latest ON latest.summary ~ '[^[:space:]]'
WHERE f.assessed_by = 'user' AND f.is_favorite
  AND w.ai_scope = 'in_scope'
  AND (w.source = 'openalex' OR (w.source = 'upload' AND w.source_url ~* '^https?://'));
REVOKE ALL ON library_display.favorite_reads FROM PUBLIC;
GRANT SELECT ON library_display.favorite_reads TO library_web_reader;
COMMIT;
