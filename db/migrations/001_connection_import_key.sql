-- Additive migration for the existing five-table database. No rows are replaced.
BEGIN;
ALTER TABLE work_connections ADD COLUMN IF NOT EXISTS import_key text;
CREATE UNIQUE INDEX IF NOT EXISTS work_connections_import_key_idx
 ON work_connections(import_key);
COMMIT;
