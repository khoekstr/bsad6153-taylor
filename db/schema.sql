-- Five-table design agreed in Database Design (November 7, 2026).
-- Run once in a NEW database; this is not a migration for the old draft.
BEGIN;
CREATE TABLE works (
 work_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 source text NOT NULL CHECK (source IN ('openalex', 'upload')),
 title text NOT NULL CHECK (length(btrim(title)) > 0),
 openalex_id text UNIQUE CHECK (openalex_id ~ '^https://openalex.org/W[0-9]+$'),
 doi text, work_type text, publication_date date,
 publication_year integer CHECK (publication_year BETWEEN 1 AND 9999),
 language text, abstract text, openalex_topic text,
 source_url text, pdf_url text, file_path text, is_open_access boolean,
 raw jsonb,
 first_seen_at timestamptz NOT NULL DEFAULT now(),
 last_updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK (source <> 'openalex' OR openalex_id IS NOT NULL),
 CHECK (source <> 'upload' OR (file_path IS NOT NULL AND length(btrim(file_path)) > 0))
);
CREATE TABLE authorships (
 authorship_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 work_id bigint NOT NULL REFERENCES works(work_id),
 author_name text NOT NULL CHECK (length(btrim(author_name)) > 0),
 author_openalex_id text CHECK (author_openalex_id ~ '^https://openalex.org/A[0-9]+$'),
 author_order integer CHECK (author_order > 0),
 first_seen_at timestamptz NOT NULL DEFAULT now(),
 last_updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (work_id, author_openalex_id),
 UNIQUE (work_id, author_order)
);
CREATE TABLE reading_notes (
 note_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 import_key text UNIQUE, -- Original chat/message identity for duplicate-free note recovery.
 work_id bigint NOT NULL REFERENCES works(work_id),
 reading_status text CHECK (reading_status IN ('not_started', 'abstract_only', 'partial', 'complete')),
 notes text, questions text, key_references text, stopped_reason text,
 read_at timestamptz,
 first_seen_at timestamptz NOT NULL DEFAULT now(),
 last_updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE work_assessments (
 assessment_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 import_key text UNIQUE, -- Stable batch/item key for duplicate-free assessment imports.
 work_id bigint NOT NULL REFERENCES works(work_id),
 assessed_by text NOT NULL CHECK (assessed_by IN ('user', 'ai')),
 -- NULL: use latest AI suggestions; empty array: user explicitly chose none.
 categories text[] CHECK (
  categories <@ ARRAY['Learning','Work','Information','Society','Technology','Discovery']::text[]
  AND array_position(categories, NULL) IS NULL),
 value_rating integer CHECK (value_rating BETWEEN 1 AND 5),
 value_reason text,
 is_favorite boolean,
 reading_status text CHECK (reading_status IN ('not_started', 'abstract_only', 'partial', 'complete')),
 come_back_to_it boolean,
 summary text,
 relevance_reason text,
 novelty_rating integer CHECK (novelty_rating BETWEEN 1 AND 5),
 novelty_reason text,
 evidence_assessment text,
 estimated_reading_minutes integer CHECK (estimated_reading_minutes > 0),
 review_basis text CHECK (review_basis IN ('metadata', 'abstract', 'excerpt', 'full_text')),
 assessment_context text,
 assessment_reason text CHECK (length(btrim(assessment_reason)) > 0),
 model_used text CHECK (length(btrim(model_used)) > 0),
 first_seen_at timestamptz NOT NULL DEFAULT now(),
 last_updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK (assessed_by <> 'ai' OR
  (review_basis IS NOT NULL AND assessment_reason IS NOT NULL AND model_used IS NOT NULL)),
 CHECK (assessed_by <> 'ai' OR
  (is_favorite IS NULL AND reading_status IS NULL AND come_back_to_it IS NULL)),
 CHECK (assessed_by <> 'user' OR model_used IS NULL)
);
CREATE TABLE work_connections (
 connection_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 import_key text, -- Stable AI pair/type key for repeatable imports.
 from_work_id bigint NOT NULL REFERENCES works(work_id),
 to_work_id bigint NOT NULL REFERENCES works(work_id),
 connection_type text NOT NULL CHECK (connection_type IN ('supports', 'challenges', 'extends', 'overlaps', 'related_topic')),
 explanation text NOT NULL CHECK (length(btrim(explanation)) > 0),
 evidence text,
 review_basis text NOT NULL CHECK (review_basis IN ('metadata', 'abstract', 'excerpt', 'full_text')),
 proposed_by text NOT NULL CHECK (proposed_by IN ('ai', 'user')),
 review_status text NOT NULL DEFAULT 'suggested' CHECK (review_status IN ('suggested', 'accepted', 'rejected')),
 user_comment text,
 first_seen_at timestamptz NOT NULL DEFAULT now(),
 last_updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK (from_work_id <> to_work_id)
);
CREATE INDEX reading_notes_work_idx ON reading_notes(work_id);
CREATE UNIQUE INDEX work_assessments_user_idx ON work_assessments(work_id)
 WHERE assessed_by = 'user';
CREATE INDEX work_assessments_latest_ai_idx ON work_assessments(work_id, first_seen_at DESC, assessment_id DESC)
 WHERE assessed_by = 'ai';
CREATE INDEX work_connections_from_idx ON work_connections(from_work_id);
CREATE INDEX work_connections_to_idx ON work_connections(to_work_id);
CREATE UNIQUE INDEX work_connections_import_key_idx ON work_connections(import_key);
CREATE FUNCTION stamp_last_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 NEW.first_seen_at := OLD.first_seen_at;
 NEW.last_updated_at := now();
 RETURN NEW;
END;
$$;
CREATE TRIGGER works_updated BEFORE UPDATE ON works
 FOR EACH ROW EXECUTE FUNCTION stamp_last_updated_at();
CREATE TRIGGER authorships_updated BEFORE UPDATE ON authorships
 FOR EACH ROW EXECUTE FUNCTION stamp_last_updated_at();
CREATE TRIGGER notes_updated BEFORE UPDATE ON reading_notes
 FOR EACH ROW EXECUTE FUNCTION stamp_last_updated_at();
CREATE TRIGGER assessments_updated BEFORE UPDATE ON work_assessments
 FOR EACH ROW EXECUTE FUNCTION stamp_last_updated_at();
CREATE TRIGGER connections_updated BEFORE UPDATE ON work_connections
 FOR EACH ROW EXECUTE FUNCTION stamp_last_updated_at();
-- Private by default. No API policies or public grants are created.
ALTER TABLE works ENABLE ROW LEVEL SECURITY;
ALTER TABLE authorships ENABLE ROW LEVEL SECURITY;
ALTER TABLE reading_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_connections ENABLE ROW LEVEL SECURITY;
COMMIT;
