export type CollectionSummary = {
  name: string;
  collection_id: string;
  status: string;
  package_hash: string | null;
  active_version_id: string | null;
  progress: Record<string, string | number | null>;
};

export type NodeKind = "group" | "text" | "table" | "image" | "file";

export type NodeSummary = {
  id: string;
  path: string;
  parent_id: string | null;
  order: number | null;
  depth: number;
  kind: NodeKind;
  title: string;
  description: string;
};

export type ResourceMetadata = {
  uri?: string;
  media_type?: string;
  sha256?: string;
  locator?: Record<string, unknown>;
  role?: string;
  description?: string;
};

export type CardMetadata = {
  spec?: string;
  id?: string;
  kind?: NodeKind;
  order?: number;
  title?: string;
  description?: string;
  source?: ResourceMetadata;
  content?: ResourceMetadata;
  assets?: ResourceMetadata[];
  table?: Record<string, unknown>;
  [key: string]: unknown;
};

export type ParsedCard = { metadata: CardMetadata; markdown: string };

export type SearchEvidence = {
  node_id: string;
  path: string;
  parent_id: string | null;
  kind: NodeKind;
  title: string;
  description: string;
  unit_type: "card" | "content_text" | "table_row";
  excerpt: string;
  row: number | null;
  line_start: number | null;
  line_end: number | null;
  locator: Record<string, unknown> | null;
};

export type SearchResult = {
  rank: number;
  score: number;
  channels: string[];
  evidence: SearchEvidence;
};

export type SearchResponse = {
  executed_mode: string;
  candidate_count: number;
  next_cursor: string | null;
  results: SearchResult[];
};
