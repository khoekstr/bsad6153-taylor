-- Preserve any existing question text before removing the separate column.
BEGIN;
DO $$
BEGIN
 IF EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'reading_notes'
              AND column_name = 'questions') THEN
  UPDATE public.reading_notes
  SET notes = concat_ws(E'\n\n', NULLIF(notes, ''), 'Questions:' || E'\n' || questions)
  WHERE NULLIF(btrim(questions), '') IS NOT NULL;
  ALTER TABLE public.reading_notes DROP COLUMN questions;
 END IF;
END $$;
COMMIT;
