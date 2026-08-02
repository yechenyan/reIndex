DROP TABLE IF EXISTS search_embeddings CASCADE;
DROP TABLE IF EXISTS unit_embeddings CASCADE;
DROP TABLE IF EXISTS search_units CASCADE;
DROP TABLE IF EXISTS embedding_profiles CASCADE;
DROP TABLE IF EXISTS node_resources CASCADE;
DROP TABLE IF EXISTS nodes CASCADE;
DROP TABLE IF EXISTS resources CASCADE;
DROP TABLE IF EXISTS raw_files CASCADE;
DROP TABLE IF EXISTS blobs CASCADE;
DROP TABLE IF EXISTS collection_revisions CASCADE;
DROP TABLE IF EXISTS collections CASCADE;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_search;

CREATE TABLE collections (
  id uuid PRIMARY KEY,
  name text NOT NULL UNIQUE,
  status text NOT NULL CHECK (status IN ('draft', 'queued', 'validating', 'indexing', 'ready', 'failed')),
  package_hash char(64),
  embedding_profile text,
  progress jsonb NOT NULL DEFAULT '{}'::jsonb,
  error jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE resources (
  id uuid PRIMARY KEY,
  collection_id uuid NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
  namespace text NOT NULL CHECK (namespace IN ('raw', 'package')),
  logical_path text NOT NULL,
  display_name text NOT NULL,
  sha256 char(64) NOT NULL,
  byte_size bigint NOT NULL CHECK (byte_size >= 0),
  media_type text NOT NULL,
  object_key text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (collection_id, namespace, logical_path),
  UNIQUE (collection_id, id)
);
CREATE INDEX resources_sha_idx ON resources (collection_id, sha256);
CREATE INDEX resources_object_idx ON resources (object_key);

CREATE TABLE nodes (
  collection_id uuid NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
  id uuid NOT NULL,
  parent_node_id uuid,
  ordinal integer,
  path text NOT NULL,
  tree_path uuid[] NOT NULL,
  order_path integer[] NOT NULL,
  kind text NOT NULL CHECK (kind IN ('group', 'text', 'table', 'image', 'file')),
  title text NOT NULL,
  description text NOT NULL,
  card_markdown text NOT NULL,
  attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
  node_hash char(64) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (collection_id, id),
  UNIQUE (collection_id, path),
  UNIQUE (collection_id, parent_node_id, ordinal),
  FOREIGN KEY (collection_id, parent_node_id)
    REFERENCES nodes(collection_id, id) DEFERRABLE INITIALLY DEFERRED,
  CHECK ((parent_node_id IS NULL AND ordinal IS NULL) OR (parent_node_id IS NOT NULL AND ordinal > 0))
);
CREATE INDEX nodes_children_idx ON nodes (collection_id, parent_node_id, ordinal);
CREATE INDEX nodes_tree_path_idx ON nodes USING gin (tree_path);
CREATE INDEX nodes_order_path_idx ON nodes (collection_id, order_path);

CREATE TABLE node_resources (
  collection_id uuid NOT NULL,
  node_id uuid NOT NULL,
  role text NOT NULL CHECK (role IN ('card', 'source', 'content', 'asset')),
  ordinal integer NOT NULL CHECK (ordinal >= 0),
  resource_id uuid NOT NULL,
  locator jsonb,
  asset_role text,
  description text,
  PRIMARY KEY (collection_id, node_id, role, ordinal),
  FOREIGN KEY (collection_id, node_id) REFERENCES nodes(collection_id, id) ON DELETE CASCADE,
  FOREIGN KEY (collection_id, resource_id) REFERENCES resources(collection_id, id),
  CHECK ((role = 'asset' AND ordinal > 0) OR (role <> 'asset' AND ordinal = 0))
);
CREATE UNIQUE INDEX node_resources_singular_idx
  ON node_resources (collection_id, node_id, role)
  WHERE role IN ('card', 'source', 'content');

CREATE TABLE embedding_profiles (
  id text PRIMARY KEY,
  model text NOT NULL,
  dimensions integer NOT NULL,
  config jsonb NOT NULL
);

CREATE TABLE search_units (
  id text PRIMARY KEY,
  collection_id uuid NOT NULL,
  node_id uuid NOT NULL,
  resource_id uuid,
  unit_type text NOT NULL CHECK (unit_type IN ('card', 'content_text', 'table_row')),
  path text NOT NULL,
  tree_path uuid[] NOT NULL,
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
  FOREIGN KEY (collection_id, node_id) REFERENCES nodes(collection_id, id) ON DELETE CASCADE,
  FOREIGN KEY (collection_id, resource_id) REFERENCES resources(collection_id, id)
);
CREATE INDEX search_units_node_idx ON search_units (collection_id, node_id);
CREATE INDEX search_units_tree_path_idx ON search_units USING gin (tree_path);
CREATE INDEX search_units_bm25_idx ON search_units
USING bm25 (
  id,
  collection_id,
  node_id,
  (path::pdb.literal),
  (kind::pdb.literal),
  (unit_type::pdb.literal),
  (title::pdb.icu),
  (description::pdb.icu),
  (original_text::pdb.icu),
  ordinal,
  row_number
)
WITH (key_field = 'id');

CREATE TABLE search_embeddings (
  search_unit_id text NOT NULL REFERENCES search_units(id) ON DELETE CASCADE,
  profile_id text NOT NULL REFERENCES embedding_profiles(id),
  embedding vector(1024) NOT NULL,
  PRIMARY KEY (search_unit_id, profile_id)
);
CREATE INDEX search_embeddings_hnsw_idx
  ON search_embeddings USING hnsw (embedding vector_cosine_ops);
