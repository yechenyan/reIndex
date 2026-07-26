CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_search;

CREATE TABLE IF NOT EXISTS collections (
  root_node_id uuid PRIMARY KEY,
  root_node jsonb,
  status text NOT NULL,
  active_revision_id uuid,
  progress jsonb NOT NULL DEFAULT '{}'::jsonb,
  error jsonb
);
ALTER TABLE collections ADD COLUMN IF NOT EXISTS root_node jsonb;

CREATE TABLE IF NOT EXISTS collection_revisions (
  id uuid PRIMARY KEY,
  collection_id uuid NOT NULL REFERENCES collections(root_node_id),
  status text NOT NULL,
  embedding_profile text,
  created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE collection_revisions ADD COLUMN IF NOT EXISTS embedding_profile text;

CREATE TABLE IF NOT EXISTS blobs (
  sha256 char(64) PRIMARY KEY,
  byte_size bigint NOT NULL,
  media_type text,
  object_key text NOT NULL
);
CREATE TABLE IF NOT EXISTS raw_files (
  collection_id uuid NOT NULL REFERENCES collections(root_node_id),
  raw_path text NOT NULL,
  sha256 char(64) NOT NULL REFERENCES blobs(sha256),
  PRIMARY KEY (collection_id, raw_path)
);

CREATE TABLE IF NOT EXISTS nodes (
  revision_id uuid NOT NULL REFERENCES collection_revisions(id),
  node_id uuid NOT NULL,
  parent_node_id uuid,
  path text NOT NULL,
  kind text NOT NULL,
  title text NOT NULL,
  description text NOT NULL,
  body text NOT NULL,
  source_uri text,
  source_sha256 char(64),
  locator jsonb,
  resource_uri text,
  resource_key text,
  table_meta jsonb,
  PRIMARY KEY (revision_id, node_id),
  UNIQUE (revision_id, path)
);
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS resource_uri text;

CREATE TABLE IF NOT EXISTS search_units (
  id text PRIMARY KEY,
  unit_id text NOT NULL,
  collection_id uuid NOT NULL REFERENCES collections(root_node_id),
  revision_id uuid NOT NULL REFERENCES collection_revisions(id),
  node_id uuid NOT NULL,
  path text NOT NULL,
  kind text NOT NULL,
  title text NOT NULL,
  description text NOT NULL,
  ordinal integer NOT NULL,
  row_number integer,
  start_line integer,
  end_line integer,
  locator jsonb,
  original_text text NOT NULL,
  contextual_text text NOT NULL,
  UNIQUE (revision_id, node_id, ordinal, row_number)
);
ALTER TABLE search_units ADD COLUMN IF NOT EXISTS collection_id uuid REFERENCES collections(root_node_id);
ALTER TABLE search_units ADD COLUMN IF NOT EXISTS unit_id text;
ALTER TABLE search_units ADD COLUMN IF NOT EXISTS path text;
ALTER TABLE search_units ADD COLUMN IF NOT EXISTS kind text;
ALTER TABLE search_units ADD COLUMN IF NOT EXISTS title text;
ALTER TABLE search_units ADD COLUMN IF NOT EXISTS description text;
ALTER TABLE search_units ADD COLUMN IF NOT EXISTS start_line integer;
ALTER TABLE search_units ADD COLUMN IF NOT EXISTS end_line integer;
ALTER TABLE search_units ADD COLUMN IF NOT EXISTS locator jsonb;
ALTER TABLE IF EXISTS unit_embeddings DROP CONSTRAINT IF EXISTS unit_embeddings_unit_id_fkey;
DO $$
BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema = current_schema() AND table_name = 'search_units' AND column_name = 'id') <> 'text' THEN
    ALTER TABLE search_units ALTER COLUMN id TYPE text USING id::text;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = current_schema() AND table_name = 'unit_embeddings'
      AND column_name = 'unit_id' AND data_type <> 'text'
  ) THEN
    ALTER TABLE unit_embeddings ALTER COLUMN unit_id TYPE text USING unit_id::text;
  END IF;
END
$$;
UPDATE search_units u
SET collection_id = r.collection_id,
    unit_id = coalesce(u.unit_id, u.id),
    path = n.path,
    kind = n.kind,
    title = n.title,
    description = n.description
FROM collection_revisions r, nodes n
WHERE u.revision_id = r.id
  AND n.revision_id = u.revision_id
  AND n.node_id = u.node_id
  AND (u.collection_id IS NULL OR u.unit_id IS NULL OR u.path IS NULL OR u.kind IS NULL OR u.title IS NULL OR u.description IS NULL);
ALTER TABLE search_units ALTER COLUMN collection_id SET NOT NULL;
ALTER TABLE search_units ALTER COLUMN unit_id SET NOT NULL;
ALTER TABLE search_units ALTER COLUMN path SET NOT NULL;
ALTER TABLE search_units ALTER COLUMN kind SET NOT NULL;
ALTER TABLE search_units ALTER COLUMN title SET NOT NULL;
ALTER TABLE search_units ALTER COLUMN description SET NOT NULL;
DROP INDEX IF EXISTS search_units_tsv_idx;
DROP INDEX IF EXISTS search_units_original_trgm_idx;
DROP INDEX IF EXISTS nodes_title_trgm_idx;
ALTER TABLE search_units DROP COLUMN IF EXISTS tsv;
CREATE INDEX IF NOT EXISTS search_units_revision_idx ON search_units (revision_id);
CREATE INDEX IF NOT EXISTS search_units_node_idx ON search_units (revision_id, node_id);
CREATE INDEX IF NOT EXISTS search_units_bm25_idx ON search_units
USING bm25 (
  id,
  collection_id,
  revision_id,
  node_id,
  (path::pdb.literal),
  (kind::pdb.literal),
  (title::pdb.icu),
  (description::pdb.icu),
  (original_text::pdb.icu),
  ordinal,
  row_number
)
WITH (key_field = 'id');

CREATE TABLE IF NOT EXISTS embedding_profiles (
  id text PRIMARY KEY,
  model text NOT NULL,
  dimensions integer NOT NULL,
  config jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS unit_embeddings (
  unit_id text NOT NULL REFERENCES search_units(id),
  profile_id text NOT NULL REFERENCES embedding_profiles(id),
  embedding vector(1024) NOT NULL,
  PRIMARY KEY (unit_id, profile_id)
);
ALTER TABLE unit_embeddings DROP CONSTRAINT IF EXISTS unit_embeddings_unit_id_fkey;
ALTER TABLE unit_embeddings ADD CONSTRAINT unit_embeddings_unit_id_fkey FOREIGN KEY (unit_id) REFERENCES search_units(id);
CREATE INDEX IF NOT EXISTS unit_embeddings_hnsw_idx
  ON unit_embeddings USING hnsw (embedding vector_cosine_ops);
