BEGIN;
ALTER TABLE reading_notes ADD COLUMN IF NOT EXISTS import_key text;
CREATE UNIQUE INDEX IF NOT EXISTS reading_notes_import_key_key ON reading_notes(import_key);
COMMIT;
