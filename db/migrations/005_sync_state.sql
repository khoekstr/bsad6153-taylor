-- Additive Part B migration. No data tables are replaced.
BEGIN;
CREATE TABLE IF NOT EXISTS public.sync_state (
  pipeline text PRIMARY KEY,
  state jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(state) = 'object'),
  last_updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.sync_state ENABLE ROW LEVEL SECURITY;
GRANT SELECT ON public.sync_state TO app_reader;
DROP POLICY IF EXISTS app_reader_select ON public.sync_state;
CREATE POLICY app_reader_select ON public.sync_state
  FOR SELECT TO app_reader USING (true);
COMMIT;
