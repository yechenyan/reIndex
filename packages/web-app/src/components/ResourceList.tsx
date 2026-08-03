import { getNodeResource } from "../api";
import type { NodeSummary, ParsedCard, ResourceMetadata } from "../types";

type Props = { card: ParsedCard; collection: string; node: NodeSummary };

export function ResourceList({ card, collection, node }: Props) {
  const resources = [
    card.metadata.source ? { label: "Source", target: "source" as const, value: card.metadata.source } : null,
    card.metadata.content ? { label: "Content", target: "content" as const, value: card.metadata.content } : null,
    ...(card.metadata.assets || []).map((value, index) => ({ label: `Asset ${index + 1}`, target: "asset" as const, ordinal: index + 1, value })),
  ].filter(Boolean) as { label: string; target: "source" | "content" | "asset"; ordinal?: number; value: ResourceMetadata }[];

  async function download(target: "source" | "content" | "asset", ordinal?: number) {
    const response = await getNodeResource(collection, node.id, target, ordinal);
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = node.title;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  if (!resources.length) return <p className="content-state">这个 Group Node 没有独立资源。</p>;
  return (
    <section className="resource-list">
      <header><p className="eyebrow">LINKED RESOURCES</p><span>{resources.length} items</span></header>
      {resources.map((item, index) => (
        <article className="resource-row" key={`${item.label}-${index}`}>
          <span className="resource-role">{item.label.slice(0, 1)}</span>
          <div>
            <strong>{item.label}</strong>
            <p>{item.value.uri || item.value.description || "Linked resource"}</p>
            <code>{item.value.sha256 ? `sha256:${item.value.sha256.slice(0, 16)}…` : "No digest"}</code>
          </div>
          <span className="resource-type">{item.value.media_type || item.value.role || "resource"}</span>
          <button onClick={() => download(item.target, item.ordinal)} type="button">下载</button>
        </article>
      ))}
    </section>
  );
}
