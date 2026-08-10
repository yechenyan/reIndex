import { useState } from "react";
import { useI18n } from "../i18n";

const agentPrompt = `You can use the ReIndex HTTP API at https://reindex-api.onrender.com.

Goal: answer the user's question using ReIndex evidence, not assumptions.

1. Call GET /v1/collections to discover available Collections. If more than one is relevant and the user did not specify one, ask which Collection to use.
2. Call POST /v1/search with {"collection":"<name>","query":"<user question>","mode":"lexical","limit":10,"candidate_limit":100,"filters":{},"ranking":{}}. Use lexical mode by default; use semantic or hybrid only when the service reports embeddings are available.
3. To discover tables, call POST /v1/nodes/browse with {"collection":"<name>","parent_node_id":null,"recursive":true}, then select nodes where kind is "table". Keep each table node's id and path.
4. To inspect a table's schema, call POST /v1/tables/query with {"collection":"<name>","node_id":"<table UUID>","sql":"SELECT * FROM data LIMIT 0","params":[]}. Read the response.columns. To inspect values, use SELECT * FROM data LIMIT 5. The table is always named data and all imported columns are strings; CAST values before numeric or date calculations.
5. To answer from a table, call POST /v1/tables/query with one read-only SELECT or WITH statement. Use params for values, add a LIMIT, and never attempt writes, multiple statements, external reads, or extensions. Include the table node path/id and the SQL used in the answer.
6. Base every answer on result.evidence or table-query rows. State the Collection and cite the returned Node path, node_id, and excerpt or query result. If evidence is insufficient, say so and refine the query instead of inventing an answer.
7. Use the API reference for exact schemas: https://reindex-web.onrender.com/#tag/Collections and https://reindex-web.onrender.com/#tag/Search.`;

export function DocHomePage() {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const entries = [
    { href: "#/doc/cli", label: "CLI Reference", title: t("docs.cli.title"), description: t("docs.cli.desc") },
    { href: "#/doc/api", label: "HTTP API Reference", title: t("docs.api.title"), description: t("docs.api.desc") },
  ];
  return (
    <section className="doc-home">
      <div className="doc-hero">
        <p className="eyebrow">CONTRACT REFERENCES</p>
        <h1>ReIndex Docs</h1>
        <p>{t("docs.intro")}</p>
      </div>
      <div className="doc-entry-grid">
        {entries.map((entry) => (
          <a className="doc-entry" href={entry.href} key={entry.href}>
            <span>{entry.label}</span>
            <h2>{entry.title}</h2>
            <p>{entry.description}</p>
            <strong>{t("docs.open")}</strong>
          </a>
        ))}
      </div>
      <section className="agent-prompt">
        <div><p className="eyebrow">FOR AI AGENTS</p><h2>Copy this prompt to use Collections, Search, and tables.</h2><p>It tells an agent how to discover a Collection, retrieve evidence, inspect table columns, and cite what it found.</p></div>
        <button onClick={() => { void navigator.clipboard.writeText(agentPrompt).then(() => setCopied(true)); }} type="button">{copied ? "Copied" : "Copy prompt"}</button>
        <pre>{agentPrompt}</pre>
      </section>
    </section>
  );
}
