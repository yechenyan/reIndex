import type { Dispatch, SetStateAction } from "react";
import type { NodeKind } from "../types";
import { useI18n } from "../i18n";

const kinds: NodeKind[] = ["group", "text", "table", "image", "file"];

export type SearchSettings = {
  mode: "lexical" | "semantic" | "hybrid";
  limit: number;
  candidateLimit: number;
  nodeIds: string;
  kinds: NodeKind[];
  pathPrefix: string;
  subtreeNodeId: string;
  lexicalWeight: number;
  semanticWeight: number;
  rrfK: number;
  maxPerNode: number;
  semanticThreshold: string;
  cursor: string;
};

type Props = { settings: SearchSettings; setSettings: Dispatch<SetStateAction<SearchSettings>> };
type NumberKey = "limit" | "candidateLimit" | "lexicalWeight" | "semanticWeight" | "rrfK" | "maxPerNode";

export function SearchOptionsPanel({ settings, setSettings }: Props) {
  const { t } = useI18n();
  const number = (key: NumberKey, value: string) => setSettings((current) => ({ ...current, [key]: Number(value) }));
  const text = (key: "nodeIds" | "pathPrefix" | "subtreeNodeId" | "semanticThreshold" | "cursor", value: string) => setSettings((current) => ({ ...current, [key]: value }));
  const toggleKind = (kind: NodeKind) => setSettings((current) => ({ ...current, kinds: current.kinds.includes(kind) ? current.kinds.filter((value) => value !== kind) : [...current.kinds, kind] }));

  return <aside className="search-filters">
    <div className="filter-heading"><p className="eyebrow">SEARCH SETTINGS</p><button onClick={() => setSettings(defaultSearchSettings())} type="button">{t("search.reset")}</button></div>
    <fieldset><legend>{t("search.mode")}</legend>{(["hybrid", "lexical", "semantic"] as const).map((value) => <label className="radio-row" key={value}><input checked={settings.mode === value} name="mode" onChange={() => setSettings((current) => ({ ...current, mode: value }))} type="radio" /><span><strong>{value}</strong><small>{t(`search.${value}`)}</small></span></label>)}</fieldset>
    <fieldset><legend>{t("search.types")}</legend>{kinds.map((kind) => <label className="check-row" key={kind}><input checked={settings.kinds.includes(kind)} onChange={() => toggleKind(kind)} type="checkbox" /><span>{kind}</span></label>)}</fieldset>
    <fieldset className="search-number-grid"><legend>Paging</legend><NumberInput label="Results" max={50} min={1} onChange={(value) => number("limit", value)} value={settings.limit} /><NumberInput label="Candidates" max={500} min={10} onChange={(value) => number("candidateLimit", value)} value={settings.candidateLimit} /></fieldset>
    <details className="search-advanced"><summary>Advanced parameters</summary><label>Node IDs (comma-separated)<input onChange={(event) => text("nodeIds", event.target.value)} placeholder="UUID, UUID" value={settings.nodeIds} /></label><label>Path prefix<input onChange={(event) => text("pathPrefix", event.target.value)} placeholder="reports/2026" value={settings.pathPrefix} /></label><label>Subtree node ID<input onChange={(event) => text("subtreeNodeId", event.target.value)} placeholder="UUID" value={settings.subtreeNodeId} /></label><div className="search-number-grid"><NumberInput label="Lexical weight" max={10} min={0} onChange={(value) => number("lexicalWeight", value)} step="0.1" value={settings.lexicalWeight} /><NumberInput label="Semantic weight" max={10} min={0} onChange={(value) => number("semanticWeight", value)} step="0.1" value={settings.semanticWeight} /><NumberInput label="RRF k" max={200} min={1} onChange={(value) => number("rrfK", value)} value={settings.rrfK} /><NumberInput label="Max per node" max={10} min={1} onChange={(value) => number("maxPerNode", value)} value={settings.maxPerNode} /></div><label>Semantic threshold<input max={1} min={-1} onChange={(event) => text("semanticThreshold", event.target.value)} placeholder="Optional: -1 to 1" step="0.01" type="number" value={settings.semanticThreshold} /></label><label>Cursor<input onChange={(event) => text("cursor", event.target.value)} placeholder="Optional next_cursor" value={settings.cursor} /></label></details>
    <div className="scope-note"><span>i</span><p>{t("search.scope")}</p></div>
  </aside>;
}

function NumberInput({ label, ...props }: { label: string; value: number; onChange: (value: string) => void; min: number; max: number; step?: string }) {
  return <label>{label}<input {...props} onChange={(event) => props.onChange(event.target.value)} type="number" /></label>;
}

export function defaultSearchSettings(): SearchSettings {
  return { mode: "hybrid", limit: 20, candidateLimit: 100, nodeIds: "", kinds: [], pathPrefix: "", subtreeNodeId: "", lexicalWeight: 0.5, semanticWeight: 1, rrfK: 60, maxPerNode: 3, semanticThreshold: "", cursor: "" };
}
