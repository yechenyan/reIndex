export function readHashParams() {
  const query = window.location.hash.split("?")[1] || "";
  return new URLSearchParams(query);
}

export function exploreHref(collection: string, nodeId: string, line?: number | null) {
  const params = new URLSearchParams({ collection, node: nodeId });
  if (line) params.set("line", String(line));
  params.set("from", "search");
  return `#/explore?${params}`;
}

export function replaceExploreHash(collection: string, nodeId?: string) {
  const params = new URLSearchParams({ collection });
  if (nodeId) params.set("node", nodeId);
  window.history.replaceState(null, "", `#/explore?${params}`);
}
