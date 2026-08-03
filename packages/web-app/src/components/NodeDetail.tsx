import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getNodeResource } from "../api";
import { parseNodeCard } from "../card";
import type { NodeSummary, ParsedCard } from "../types";
import { ContentPreview } from "./ContentPreview";
import { ResourceList } from "./ResourceList";
import { StatusPanel } from "./StatusPanel";

type Tab = "card" | "content" | "resources";
type Props = { collection: string; node: NodeSummary | null };

export function NodeDetail({ collection, node }: Props) {
  const [tab, setTab] = useState<Tab>("card");
  const [card, setCard] = useState<ParsedCard | null>(null);
  const [status, setStatus] = useState("loading");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!node) return;
    let active = true;
    setTab("card");
    setCard(null);
    setStatus("loading");
    getNodeResource(collection, node.id, "card")
      .then((response) => response.text())
      .then((source) => {
        if (!active) return;
        setCard(parseNodeCard(source));
        setStatus("ready");
      })
      .catch((error: Error) => active && setStatus(error.message));
    return () => { active = false; };
  }, [collection, node]);

  if (!node) return <StatusPanel title="选择一个 Node" message="从左侧 Collection tree 中选择需要查看的数据。" />;
  if (status === "loading") return <StatusPanel title="读取数据卡" message={`正在加载 ${node.title}…`} />;
  if (status !== "ready" || !card) return <StatusPanel title="无法读取 Node" message={status} />;

  const command = `rei get ${node.path} --target content --remote ${collection}`;
  async function copyCommand() {
    await navigator.clipboard.writeText(command);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <article className="node-detail">
      <header className="node-header">
        <div>
          <p className="breadcrumb">{collection} <span>/</span> {node.path}</p>
          <div className="node-title-line">
            <span className={`kind-badge kind-${node.kind}`}>{node.kind}</span>
            <h1>{node.title}</h1>
          </div>
          <p className="node-description">{node.description}</p>
        </div>
        <button className="copy-command" onClick={copyCommand} type="button">
          {copied ? "已复制" : "复制 rei get"}
        </button>
      </header>
      <nav className="detail-tabs" aria-label="Node 详情">
        {(["card", "content", "resources"] as Tab[]).map((value) => (
          <button className={tab === value ? "active" : ""} key={value} onClick={() => setTab(value)} type="button">
            {{ card: "数据卡", content: "内容预览", resources: "资源" }[value]}
          </button>
        ))}
      </nav>
      <div className="detail-body">
        {tab === "card" ? (
          <div className="card-layout">
            <section className="markdown-body">
              {card.markdown ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{card.markdown}</ReactMarkdown> : <p>这个 Node 暂无数据卡正文。</p>}
            </section>
            <aside className="metadata-rail">
              <p className="eyebrow">NODE METADATA</p>
              <dl>
                <div><dt>ID</dt><dd>{node.id}</dd></div>
                <div><dt>Kind</dt><dd>{node.kind}</dd></div>
                <div><dt>Order</dt><dd>{node.order ?? "Root"}</dd></div>
                <div><dt>Protocol</dt><dd>{card.metadata.spec || "reindex/node@1.0"}</dd></div>
              </dl>
            </aside>
          </div>
        ) : null}
        {tab === "content" ? <ContentPreview card={card} collection={collection} node={node} /> : null}
        {tab === "resources" ? <ResourceList card={card} collection={collection} node={node} /> : null}
      </div>
    </article>
  );
}
