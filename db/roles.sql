-- Run as postgres. Safe to rerun; never put a password in this file.
-- Set the login password separately in the Supabase SQL editor.
BEGIN;
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_reader') THEN
    CREATE ROLE app_reader LOGIN NOINHERIT;
  END IF;
END
$$;
-- New roles default to no elevated privileges. Supabase's postgres role cannot
-- explicitly alter superuser/replication/bypass flags, even to turn them off.
ALTER ROLE app_reader LOGIN NOINHERIT;
-- Fail rather than silently retain unexpected membership or ownership.
DO $$
BEGIN
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_reader'
             AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
     OR EXISTS (SELECT FROM pg_auth_members WHERE member = 'app_reader'::regrole)
     OR EXISTS (SELECT FROM pg_class WHERE relowner = 'app_reader'::regrole)
     OR EXISTS (SELECT FROM pg_namespace WHERE nspowner = 'app_reader'::regrole)
  THEN
    RAISE EXCEPTION 'app_reader must not own objects or belong to other roles';
  END IF;
END
$$;
REVOKE ALL ON SCHEMA public FROM app_reader;
GRANT USAGE ON SCHEMA public TO app_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM app_reader;
GRANT SELECT ON public.works, public.authorships, public.reading_notes,
  public.work_assessments, public.work_connections TO app_reader;

-- RLS remains enabled. Only this private application role gets read policies.
DROP POLICY IF EXISTS app_reader_select ON public.works;
CREATE POLICY app_reader_select ON public.works FOR SELECT TO app_reader USING (true);
DROP POLICY IF EXISTS app_reader_select ON public.authorships;
CREATE POLICY app_reader_select ON public.authorships FOR SELECT TO app_reader USING (true);
DROP POLICY IF EXISTS app_reader_select ON public.reading_notes;
CREATE POLICY app_reader_select ON public.reading_notes FOR SELECT TO app_reader USING (true);
DROP POLICY IF EXISTS app_reader_select ON public.work_assessments;
CREATE POLICY app_reader_select ON public.work_assessments FOR SELECT TO app_reader USING (true);
DROP POLICY IF EXISTS app_reader_select ON public.work_connections;
CREATE POLICY app_reader_select ON public.work_connections FOR SELECT TO app_reader USING (true);

-- Add an explicit SELECT grant for each new data table, starting with sync_runs,
-- sync_state is introduced by migration 005; skip it on pre-migration databases.
DO $$
BEGIN
  IF to_regclass('public.sync_runs') IS NOT NULL THEN
    GRANT SELECT ON public.sync_runs TO app_reader;
    DROP POLICY IF EXISTS app_reader_select ON public.sync_runs;
    CREATE POLICY app_reader_select ON public.sync_runs FOR SELECT TO app_reader USING (true);
  END IF;
  IF to_regclass('public.sync_state') IS NOT NULL THEN
    GRANT SELECT ON public.sync_state TO app_reader;
    DROP POLICY IF EXISTS app_reader_select ON public.sync_state;
    CREATE POLICY app_reader_select ON public.sync_state FOR SELECT TO app_reader USING (true);
  END IF;
END
$$;
-- and a matching SELECT policy if RLS is enabled. Then rerun this file.
-- No blanket grants on future tables: they require an explicit access decision.
COMMIT;
