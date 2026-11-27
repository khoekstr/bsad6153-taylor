-- Apply after 009, as administrator. Prepared locally; not applied automatically.
BEGIN;
ALTER TABLE public.reading_notes ALTER COLUMN work_id DROP NOT NULL;
ALTER TABLE public.reading_notes ADD COLUMN deleted_at timestamptz;
CREATE TABLE public.note_history (
 revision_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 note_id bigint NOT NULL REFERENCES public.reading_notes,
 snapshot jsonb NOT NULL, changed_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.note_history ENABLE ROW LEVEL SECURITY;
CREATE FUNCTION public.archive_note_revision() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
 INSERT INTO public.note_history(note_id,snapshot) VALUES (OLD.note_id,to_jsonb(OLD));
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION public.archive_note_revision() FROM PUBLIC;
CREATE TRIGGER archive_note BEFORE UPDATE ON public.reading_notes
 FOR EACH ROW EXECUTE FUNCTION public.archive_note_revision();
GRANT SELECT (deleted_at,last_updated_at), UPDATE (notes,quoted_passage,key_references,deleted_at)
 ON public.reading_notes TO library_notebook;
CREATE POLICY notebook_edit ON public.reading_notes FOR UPDATE TO library_notebook
 USING (true) WITH CHECK (true);
GRANT SELECT ON public.note_history TO library_notebook;
CREATE POLICY notebook_history ON public.note_history FOR SELECT TO library_notebook USING (true);
GRANT SELECT ON public.work_assessments TO library_notebook;
GRANT INSERT (work_id,assessed_by,value_rating,value_reason,is_favorite,come_back_to_it,reading_status),
 UPDATE (value_rating,value_reason,is_favorite,come_back_to_it,reading_status)
 ON public.work_assessments TO library_notebook;
CREATE POLICY notebook_assess_read ON public.work_assessments FOR SELECT TO library_notebook USING (true);
CREATE POLICY notebook_assess_insert ON public.work_assessments FOR INSERT TO library_notebook WITH CHECK (assessed_by='user');
CREATE POLICY notebook_assess_update ON public.work_assessments FOR UPDATE TO library_notebook
 USING (assessed_by='user') WITH CHECK (assessed_by='user');
GRANT SELECT ON public.work_connections TO library_notebook;
CREATE POLICY notebook_connections ON public.work_connections FOR SELECT TO library_notebook USING (true);
GRANT SELECT (publication_name,is_retracted) ON public.works TO library_web_reader;
CREATE TABLE public.recommendation_feedback (
 singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
 feedback jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.recommendation_feedback ENABLE ROW LEVEL SECURITY;
GRANT SELECT,INSERT,UPDATE ON public.recommendation_feedback TO library_notebook;
CREATE POLICY notebook_feedback ON public.recommendation_feedback TO library_notebook USING(true) WITH CHECK(true);
COMMIT;
