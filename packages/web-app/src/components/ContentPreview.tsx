import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getNodeResource } from "../api";
import type { NodeSummary, ParsedCard } from "../types";
import { useI18n } from "../i18n";

type Props = { card: ParsedCard; collection: string; node: NodeSummary };

export function ContentPreview({ card, collection, node }: Props) {
  const { t } = useI18n();
  const [content, setContent] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    if (!card.metadata.content || node.kind === "group") {
      setStatus("empty");
      return;
    }
    let active = true;
    let objectUrl = "";
    setStatus("loading");
    getNodeResource(collection, node.id, "content")
      .then(async (response) => {
        const type = response.headers.get("content-type") || card.metadata.content?.media_type || "";
        if (type.startsWith("image/")) {
          objectUrl = URL.createObjectURL(await response.blob());
          if (active) setImageUrl(objectUrl);
        } else if (active) setContent(await response.text());
      })
      .then(() => active && setStatus("ready"))
      .catch((error: Error) => active && setStatus(error.message));
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [card, collection, node]);

  if (status === "loading") return <p className="content-state">{t("content.loading")}</p>;
  if (status === "empty") return <p className="content-state">{t("content.empty")}</p>;
  if (status !== "ready") return <p className="content-state error">{status}</p>;
  if (imageUrl) return <figure className="image-preview"><img alt={node.title} src={imageUrl} /><figcaption>{node.title}</figcaption></figure>;
  if (node.kind === "table") return <CsvPreview source={content} />;
  if (card.metadata.content?.media_type === "text/markdown") {
    return <section className="markdown-body content-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown></section>;
  }
  return <pre className="raw-preview">{content}</pre>;
}

function CsvPreview({ source }: { source: string }) {
  const { t } = useI18n();
  const rows = source.trim().split(/\r?\n/).slice(0, 12).map(parseCsvRow);
  if (!rows.length) return <p className="content-state">{t("content.tableEmpty")}</p>;
  return (
    <div className="table-preview">
      <div className="preview-note">{t("content.rows", { count: Math.max(rows.length - 1, 0) })}</div>
      <div className="table-scroll">
        <table>
          <thead><tr>{rows[0].map((cell, index) => <th key={`${cell}-${index}`}>{cell}</th>)}</tr></thead>
          <tbody>{rows.slice(1).map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, index) => <td key={index}>{cell}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

function parseCsvRow(row: string) {
  const cells: string[] = [];
  let value = "";
  let quoted = false;
  for (let index = 0; index < row.length; index += 1) {
    const char = row[index];
    if (char === '"' && row[index + 1] === '"') { value += '"'; index += 1; }
    else if (char === '"') quoted = !quoted;
    else if (char === "," && !quoted) { cells.push(value); value = ""; }
    else value += char;
  }
  cells.push(value);
  return cells;
}
