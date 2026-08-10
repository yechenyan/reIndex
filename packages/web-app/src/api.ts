import type {
  CollectionSummary,
  NodeKind,
  NodeSummary,
  SearchResponse,
  TableQueryResponse,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const SERVICE_UNAVAILABLE_MESSAGE = "当前为测试阶段，为节省服务端成本，当前服务端暂时关闭";

async function request(path: string, init?: RequestInit) {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new Error(SERVICE_UNAVAILABLE_MESSAGE);
  }
  if (!response.ok) {
    if ([502, 503, 504].includes(response.status)) throw new Error(SERVICE_UNAVAILABLE_MESSAGE);
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message || `ReIndex API ${response.status}`);
  }
  return response;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return response.json() as Promise<T>;
}

export async function listCollections() {
  const response = await request("/v1/collections");
  const payload = (await response.json()) as { collections: CollectionSummary[] };
  return payload.collections;
}

export async function browseNodes(collection: string) {
  const payload = await postJson<{ nodes: NodeSummary[] }>("/v1/nodes/browse", {
    collection,
    parent_node_id: null,
    recursive: true,
  });
  return payload.nodes;
}

export async function getNodeResource(
  collection: string,
  nodeId: string,
  target: "card" | "source" | "content" | "asset",
  assetOrdinal?: number,
) {
  return request("/v1/get", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      collection,
      node_id: nodeId,
      target,
      ...(assetOrdinal ? { asset_ordinal: assetOrdinal } : {}),
    }),
  });
}

export type SearchInput = {
  collection: string;
  query: string;
  mode: "lexical" | "semantic" | "hybrid";
  limit: number;
  candidateLimit: number;
  nodeIds: string[];
  kinds: NodeKind[];
  pathPrefix?: string;
  subtreeNodeId?: string;
  lexicalWeight: number;
  semanticWeight: number;
  rrfK: number;
  maxPerNode: number;
  semanticThreshold?: number;
  cursor?: string;
};

export function searchNodes(input: SearchInput) {
  return postJson<SearchResponse>("/v1/search", {
    collection: input.collection,
    query: input.query,
    mode: input.mode,
    limit: input.limit,
    candidate_limit: input.candidateLimit,
    ...(input.cursor ? { cursor: input.cursor } : {}),
    filters: {
      node_ids: input.nodeIds,
      kinds: input.kinds,
      ...(input.pathPrefix ? { path_prefix: input.pathPrefix } : {}),
      ...(input.subtreeNodeId ? { subtree_node_id: input.subtreeNodeId } : {}),
    },
    ranking: {
      lexical_weight: input.lexicalWeight,
      semantic_weight: input.semanticWeight,
      rrf_k: input.rrfK,
      max_per_node: input.maxPerNode,
      ...(input.semanticThreshold === undefined ? {} : { semantic_threshold: input.semanticThreshold }),
    },
  });
}

export function queryTable(input: { collection: string; nodeId: string; sql: string }) {
  return postJson<TableQueryResponse>("/v1/tables/query", {
    collection: input.collection,
    node_id: input.nodeId,
    sql: input.sql,
  });
}
