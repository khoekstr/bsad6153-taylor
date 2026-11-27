-- Run as administrator inside the ratings import transaction.
-- The public reader sees the curated collection. The owner notebook keeps access.
ALTER TABLE public.works ADD COLUMN IF NOT EXISTS ai_scope text
    CHECK (ai_scope IN ('in_scope', 'excluded', 'unverified'));

DROP POLICY IF EXISTS web_curated_collection ON public.works;
CREATE POLICY web_curated_collection ON public.works AS RESTRICTIVE
    FOR SELECT TO library_web_reader
    USING (ai_scope = 'in_scope');
