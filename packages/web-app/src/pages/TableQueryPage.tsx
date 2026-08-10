import { FormEvent, useEffect, useMemo, useState } from "react";
import { browseNodes, listCollections, queryTable } from "../api";
import type { CollectionSummary, NodeSummary, TableQueryResponse } from "../types";

const exampleSql = "SELECT * FROM data LIMIT 100";

export function TableQueryPage() {
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [collection, setCollection] = useState("");
  const [nodes, setNodes] = useState<NodeSummary[]>([]);
  const [nodeId, setNodeId] = useState("");
  const [sql, setSql] = useState(exampleSql);
  const [result, setResult] = useState<TableQueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const tables = useMemo(() => nodes.filter((node) => node.kind === "table"), [nodes]);

  useEffect(() => {
    listCollections().then((items) => {
      setCollections(items);
      setCollection(items[0]?.name || "");
    }).catch((reason: Error) => setError(reason.message));
  }, []);

  useEffect(() => {
    if (!collection) return;
    browseNodes(collection).then((items) => {
      const next = items.filter((node) => node.kind === "table");
      setNodes(items);
      setNodeId(next[0]?.id || "");
    }).catch((reason: Error) => setError(reason.message));
  }, [collection]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!collection || !nodeId || !sql.trim()) return;
    setLoading(true);
    setError("");
    try {
      setResult(await queryTable({ collection, nodeId, sql: sql.trim() }));
    } catch (reason) {
      setResult(null);
      setError(reason instanceof Error ? reason.message : "Table query failed");
    } finally {
      setLoading(false);
    }
  }

  return <div className="table-query-page">
    <section className="table-query-hero">
      <p className="eyebrow">TABLE QUERY</p>
      <h1>Query an active table.</h1>
      <p>Run one read-only SQL SELECT or CTE against a table node. The selected CSV is available as <code>data</code>.</p>
    </section>
    <form className="table-query-form" onSubmit={submit}>
      <label>Collection<select value={collection} onChange={(event) => setCollection(event.target.value)}>{collections.map((item) => <option key={item.collection_id} value={item.name}>{item.name}</option>)}</select></label>
      <label>Table node<select value={nodeId} onChange={(event) => setNodeId(event.target.value)}>{tables.map((node) => <option key={node.id} value={node.id}>{node.path || node.title}</option>)}</select></label>
      <label className="sql-editor">SQL<textarea onChange={(event) => setSql(event.target.value)} spellCheck="false" value={sql} /></label>
      <button disabled={!collection || !nodeId || !sql.trim() || loading} type="submit">{loading ? "Running…" : "Run query"}<i>→</i></button>
    </form>
    {error && <p className="table-query-error">{error}</p>}
    {result && <section className="table-query-result"><header><strong>{result.rows.length} rows</strong>{result.truncated && <span>Limited to 1,000 rows</span>}</header><div><table><thead><tr>{result.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{result.rows.map((row, index) => <tr key={index}>{result.columns.map((column) => <td key={column}>{String(row[column] ?? "")}</td>)}</tr>)}</tbody></table></div></section>}
  </div>;
}
