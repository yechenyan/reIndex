import type {
  CollectionSummary,
  NodeKind,
  NodeSummary,
  SearchResponse,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

async function request(path: string, init?: RequestInit) {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
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
  kinds: NodeKind[];
  cursor?: string;
};

export function searchNodes(input: SearchInput) {
  return postJson<SearchResponse>("/v1/search", {
    collection: input.collection,
    query: input.query,
    mode: input.mode,
    limit: 20,
    candidate_limit: 100,
    ...(input.cursor ? { cursor: input.cursor } : {}),
    filters: { kinds: input.kinds },
  });
}
