-- Additive Part C migration; run once as postgres.
BEGIN;
CREATE TABLE sync_runs (
 run_id uuid PRIMARY KEY,
 started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 finished_at timestamptz,
 status text NOT NULL CHECK (status IN ('success','partial','failed')),
 records_fetched integer NOT NULL DEFAULT 0 CHECK (records_fetched >= 0),
 records_inserted integer NOT NULL DEFAULT 0 CHECK (records_inserted >= 0),
 records_updated integer NOT NULL DEFAULT 0 CHECK (records_updated >= 0),
 error_message text,
 trigger text NOT NULL CHECK (trigger IN ('schedule','manual')),
 dry_run boolean NOT NULL DEFAULT false,
 mode text NOT NULL CHECK (mode IN ('discovery_only','targeted_refresh')),
 outcome text NOT NULL DEFAULT 'unfinished',
 details jsonb NOT NULL DEFAULT '{}'::jsonb,
 CHECK (finished_at IS NULL OR finished_at >= started_at),
 CHECK (finished_at IS NOT NULL OR status = 'failed'),
 CHECK (NOT dry_run OR (records_inserted = 0 AND records_updated = 0))
);
CREATE INDEX sync_runs_started_idx ON sync_runs(started_at DESC);
ALTER TABLE sync_runs ENABLE ROW LEVEL SECURITY;
GRANT SELECT ON sync_runs TO app_reader;
CREATE POLICY app_reader_select ON sync_runs FOR SELECT TO app_reader USING (true);
COMMIT;
