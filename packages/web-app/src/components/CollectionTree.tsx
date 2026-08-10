import { useEffect, useMemo, useState } from "react";
import type { CollectionSummary, NodeSummary } from "../types";
import { useI18n } from "../i18n";

type Props = {
  collections: CollectionSummary[];
  selectedCollection: string;
  selectedNodeId: string;
  nodes: NodeSummary[];
  loading: boolean;
  onCollection: (name: string) => void;
  onNode: (node: NodeSummary) => void;
};

const kindMark: Record<string, string> = {
  group: "G",
  text: "T",
  table: "#",
  image: "I",
  file: "F",
};

export function CollectionTree(props: Props) {
  const { t } = useI18n();
  const [filter, setFilter] = useState("");
  const [open, setOpen] = useState<Set<string>>(new Set());
  const { nodes } = props;

  useEffect(() => {
    setOpen(new Set(nodes.filter((node) => node.kind === "group").map((node) => node.id)));
  }, [nodes]);

  const visibleNodes = useMemo(() => {
    const query = filter.trim().toLocaleLowerCase();
    const byId = new Map(nodes.map((node) => [node.id, node]));
    if (query) {
      const keep = new Set<string>();
      nodes.forEach((node) => {
        if (`${node.title} ${node.description}`.toLocaleLowerCase().includes(query)) {
          let current: NodeSummary | undefined = node;
          while (current) {
            keep.add(current.id);
            current = current.parent_id ? byId.get(current.parent_id) : undefined;
          }
        }
      });
      return nodes.filter((node) => keep.has(node.id));
    }
    return nodes.filter((node) => {
      let parentId = node.parent_id;
      while (parentId) {
        if (!open.has(parentId)) return false;
        parentId = byId.get(parentId)?.parent_id || null;
      }
      return true;
    });
  }, [filter, nodes, open]);

  function toggle(nodeId: string) {
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }

  return (
    <aside className="tree-panel">
      <div className="tree-heading">
        <p className="eyebrow">COLLECTIONS &amp; NODES</p>
        <span>{props.collections.length} collections</span>
      </div>
      <label className="tree-filter">
        <span aria-hidden="true">⌕</span>
        <input
          onChange={(event) => setFilter(event.target.value)}
          placeholder={t("tree.filter")}
          value={filter}
        />
      </label>
      <div className="collection-list">
        {props.collections.map((collection) => {
          const active = collection.name === props.selectedCollection;
          const count = Number(collection.progress.nodes || 0);
          return (
            <section className={active ? "collection-item active" : "collection-item"} key={collection.collection_id}>
              <button className="collection-button" onClick={() => props.onCollection(collection.name)} type="button">
                <span className="collection-icon">C</span>
                <span><strong>{collection.name}</strong><small>{collection.status}</small></span>
                <em>{count || "—"}</em>
              </button>
              {active ? (
                <div className="node-tree" aria-busy={props.loading}>
                  {visibleNodes.map((node) => (
                    <div
                      className={node.id === props.selectedNodeId ? "node-row selected" : "node-row"}
                      key={node.id}
                      style={{ paddingLeft: `${14 + node.depth * 18}px` }}
                    >
                      {node.kind === "group" ? (
                        <button className="tree-toggle" onClick={() => toggle(node.id)} type="button">
                          {open.has(node.id) ? "⌄" : "›"}
                        </button>
                      ) : <span className="tree-toggle spacer" />}
                      <button className="node-button" onClick={() => props.onNode(node)} type="button">
                        <i>{kindMark[node.kind]}</i><span>{node.title}</span>
                      </button>
                    </div>
                  ))}
                  {!props.loading && !visibleNodes.length ? <p className="tree-empty">{t("tree.empty")}</p> : null}
                </div>
              ) : null}
            </section>
          );
        })}
      </div>
    </aside>
  );
}
