-- Existing minutes field means full-article reading time; NULL means unknown.
BEGIN;
ALTER TABLE work_assessments ADD COLUMN IF NOT EXISTS estimated_reading_basis text;
COMMENT ON COLUMN work_assessments.estimated_reading_minutes IS
 'Estimated full-article reading minutes, not abstract reading time. NULL means unknown.';
COMMENT ON COLUMN work_assessments.estimated_reading_basis IS
 'Length source and assumptions used for the reading-time estimate.';
COMMIT;
