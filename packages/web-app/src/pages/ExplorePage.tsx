import { useEffect, useState } from "react";
import { browseNodes, listCollections } from "../api";
import { CollectionTree } from "../components/CollectionTree";
import { NodeDetail } from "../components/NodeDetail";
import { StatusPanel } from "../components/StatusPanel";
import { readHashParams, replaceExploreHash } from "../route";
import type { CollectionSummary, NodeSummary } from "../types";

export function ExplorePage() {
  const initial = readHashParams();
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [collectionName, setCollectionName] = useState(initial.get("collection") || "");
  const [nodes, setNodes] = useState<NodeSummary[]>([]);
  const [selectedNode, setSelectedNode] = useState<NodeSummary | null>(null);
  const [status, setStatus] = useState("loading");
  const [treeLoading, setTreeLoading] = useState(false);

  useEffect(() => {
    let active = true;
    listCollections()
      .then((items) => {
        if (!active) return;
        setCollections(items);
        const requested = initial.get("collection");
        const next = items.some((item) => item.name === requested) ? requested! : items[0]?.name || "";
        setCollectionName(next);
        setStatus(items.length ? "ready" : "empty");
      })
      .catch((error: Error) => active && setStatus(error.message));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!collectionName) return;
    let active = true;
    setTreeLoading(true);
    browseNodes(collectionName)
      .then((items) => {
        if (!active) return;
        setNodes(items);
        const requestedId = initial.get("node");
        const next = items.find((item) => item.id === requestedId) || items[0] || null;
        setSelectedNode(next);
        replaceExploreHash(collectionName, next?.id);
      })
      .catch((error: Error) => active && setStatus(error.message))
      .finally(() => active && setTreeLoading(false));
    return () => { active = false; };
  }, [collectionName]);

  function selectCollection(name: string) {
    if (name === collectionName) return;
    setNodes([]);
    setSelectedNode(null);
    setCollectionName(name);
    replaceExploreHash(name);
  }

  function selectNode(node: NodeSummary) {
    setSelectedNode(node);
    replaceExploreHash(collectionName, node.id);
  }

  if (status === "loading") return <StatusPanel title="连接 ReIndex" message="正在读取 Collection 目录…" />;
  if (status === "empty") return <StatusPanel title="还没有 Collection" message="使用 rei push 发布第一个 Collection 后，它会出现在这里。" />;
  if (status !== "ready") return <StatusPanel title="Explore 暂不可用" message={status} />;

  const current = collections.find((item) => item.name === collectionName);
  return (
    <div className="explore-page">
      <section className="page-intro">
        <div><p className="eyebrow">LIVE DATA EXPLORER</p><h1>浏览可追溯的知识结构。</h1></div>
        <div className="collection-stats">
          <span><strong>{current?.progress.nodes || nodes.length}</strong> Nodes</span>
          <span><strong>{current?.progress.resources || 0}</strong> Resources</span>
          <span><i /> {current?.status || "ready"}</span>
        </div>
      </section>
      <section className="explore-grid">
        <CollectionTree
          collections={collections}
          loading={treeLoading}
          nodes={nodes}
          onCollection={selectCollection}
          onNode={selectNode}
          selectedCollection={collectionName}
          selectedNodeId={selectedNode?.id || ""}
        />
        <NodeDetail collection={collectionName} node={selectedNode} />
      </section>
    </div>
  );
}
