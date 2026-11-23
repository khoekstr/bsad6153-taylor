-- Apply once as database administrator after migrations 001-008.
-- New roles have no passwords until the administrator provisions them separately.
BEGIN;
ALTER TABLE public.reading_notes ADD COLUMN IF NOT EXISTS quoted_passage text;
CREATE ROLE library_web_reader LOGIN NOINHERIT;
CREATE ROLE library_notebook LOGIN NOINHERIT;
GRANT USAGE ON SCHEMA public TO library_web_reader, library_notebook;

-- The local app_reader retains its historical permissions for course evaluations.
GRANT SELECT (work_id, title, publication_date, first_seen_at, openalex_topic,
              source, source_url, doi, openalex_id, abstract)
  ON public.works TO library_web_reader;
CREATE POLICY web_public_works ON public.works FOR SELECT TO library_web_reader
  USING (source = 'openalex' OR (source = 'upload' AND source_url ~* '^https?://'));

GRANT SELECT (work_id, value_rating, summary, value_reason, relevance_reason,
              review_basis, categories, assessed_by, first_seen_at, assessment_id)
  ON public.work_assessments TO library_web_reader;
CREATE POLICY web_public_assessments ON public.work_assessments FOR SELECT TO library_web_reader
  USING (assessed_by = 'ai' AND EXISTS (
    SELECT 1 FROM public.works w WHERE w.work_id = work_assessments.work_id
  ));

GRANT SELECT (finished_at, status, dry_run, mode, outcome)
  ON public.sync_runs TO library_web_reader;
CREATE POLICY web_discovery_history ON public.sync_runs FOR SELECT TO library_web_reader
  USING (status = 'success' AND NOT dry_run AND mode = 'discovery_only'
         AND outcome = 'completed' AND finished_at IS NOT NULL);

-- All legacy entries in this single-owner library belong to Kara.
GRANT SELECT (work_id, title, source_url, doi, openalex_id)
  ON public.works TO library_notebook;
CREATE POLICY notebook_paper_links ON public.works FOR SELECT TO library_notebook USING (true);
GRANT SELECT (note_id, work_id, import_key, notes, quoted_passage, key_references,
              reading_status, stopped_reason, read_at, first_seen_at),
      INSERT (work_id, import_key, notes, quoted_passage, key_references, reading_status, read_at)
  ON public.reading_notes TO library_notebook;
CREATE POLICY notebook_read ON public.reading_notes FOR SELECT TO library_notebook USING (true);
CREATE POLICY notebook_append ON public.reading_notes FOR INSERT TO library_notebook
  WITH CHECK (import_key LIKE 'notebook:%'
              AND (notes IS NOT NULL OR quoted_passage IS NOT NULL OR reading_status IS NOT NULL));
COMMIT;
