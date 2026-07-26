CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE TABLE IF NOT EXISTS collections (
  root_node_id uuid PRIMARY KEY,
  status text NOT NULL,
  active_revision_id uuid,
  progress jsonb NOT NULL DEFAULT '{}'::jsonb,
  error jsonb
);
CREATE TABLE IF NOT EXISTS collection_revisions (
  id uuid PRIMARY KEY,
  collection_id uuid NOT NULL REFERENCES collections(root_node_id),
  status text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
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
  resource_key text,
  table_meta jsonb,
  PRIMARY KEY (revision_id, node_id),
  UNIQUE (revision_id, path)
);
CREATE TABLE IF NOT EXISTS search_units (
  id uuid PRIMARY KEY,
  revision_id uuid NOT NULL,
  node_id uuid NOT NULL,
  ordinal integer NOT NULL,
  row_number integer,
  original_text text NOT NULL,
  contextual_text text NOT NULL,
  tsv tsvector NOT NULL,
  UNIQUE (revision_id, node_id, ordinal)
);
CREATE INDEX IF NOT EXISTS search_units_tsv_idx ON search_units USING gin(tsv);
CREATE INDEX IF NOT EXISTS nodes_title_trgm_idx ON nodes USING gin(title gin_trgm_ops);
CREATE TABLE IF NOT EXISTS embedding_profiles (
  id text PRIMARY KEY,
  model text NOT NULL,
  dimensions integer NOT NULL,
  config jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS unit_embeddings (
  unit_id uuid NOT NULL REFERENCES search_units(id),
  profile_id text NOT NULL REFERENCES embedding_profiles(id),
  embedding vector(1024) NOT NULL,
  PRIMARY KEY (unit_id, profile_id)
);
CREATE INDEX IF NOT EXISTS unit_embeddings_hnsw_idx
  ON unit_embeddings USING hnsw (embedding vector_cosine_ops);
