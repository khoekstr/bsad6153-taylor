-- Preserve existing narrative content before removing retired assessment fields.
BEGIN;
SET LOCAL lock_timeout = '5s';
UPDATE work_assessments
SET summary = concat_ws(E'\n\n', nullif(summary,''), 'Qualifications: ' || btrim(evidence_assessment))
WHERE nullif(btrim(evidence_assessment),'') IS NOT NULL
  AND position(btrim(evidence_assessment) in coalesce(summary,'')) = 0;
UPDATE work_assessments
SET assessment_context = concat_ws(E'\n\n', nullif(assessment_context,''),
    'Historical novelty note: ' || btrim(novelty_reason))
WHERE nullif(btrim(novelty_reason),'') IS NOT NULL
  AND position(btrim(novelty_reason) in coalesce(assessment_context,'')) = 0;
-- Do not silently discard any unexpected numeric ratings.
DO $$ BEGIN
 IF EXISTS (SELECT FROM work_assessments WHERE novelty_rating IS NOT NULL) THEN
  RAISE EXCEPTION 'Nonempty novelty scores require review before removal';
 END IF;
END $$;
ALTER TABLE work_assessments DROP COLUMN novelty_rating,
 DROP COLUMN novelty_reason, DROP COLUMN evidence_assessment;
COMMIT;
