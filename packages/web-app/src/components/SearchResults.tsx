import { exploreHref } from "../route";
import { SERVICE_UNAVAILABLE_MESSAGE } from "../api";
import { ServiceStartRequest } from "./StatusPanel";
import type { SearchEvidence, SearchResult } from "../types";
import { useI18n } from "../i18n";

type Props = {
  collection: string;
  results: SearchResult[];
  searched: boolean;
  loading: boolean;
  error: string;
  query: string;
  nextCursor: string | null;
  onMore: () => void;
};

function searchTerms(query: string) {
  const values = query.match(/[\p{Script=Han}]+|[\p{L}\p{N}][\p{L}\p{N}_./+-]*/gu) || [];
  return [...new Set(values.map((value) => value.toLocaleLowerCase()))]
    .sort((left, right) => right.length - left.length);
}

function HighlightText({ text, query }: { text: string; query: string }) {
  const terms = searchTerms(query);
  if (!terms.length) return text;
  const patterns = terms.map((term) => {
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return /\p{Script=Han}/u.test(term)
      ? escaped
      : `(?<![\\p{L}\\p{N}_])${escaped}(?![\\p{L}\\p{N}_])`;
  });
  const expression = new RegExp(`(${patterns.join("|")})`, "giu");
  const matches = new Set(terms);
  return text.split(expression).map((part, index) =>
    matches.has(part.toLocaleLowerCase())
      ? <mark className="search-highlight" key={`${part}-${index}`}>{part}</mark>
      : part,
  );
}

function tableCells(excerpt: string) {
  return excerpt.split(" | ").flatMap((part) => {
    const separator = part.indexOf(": ");
    if (separator < 1) return [];
    return [{ label: part.slice(0, separator), value: part.slice(separator + 2) }];
  });
}

function EvidencePreview({ evidence, query }: { evidence: SearchEvidence; query: string }) {
  if (evidence.unit_type !== "table_row") {
    return <blockquote><HighlightText query={query} text={evidence.excerpt} /></blockquote>;
  }
  const cells = tableCells(evidence.excerpt);
  if (!cells.length) return <blockquote><HighlightText query={query} text={evidence.excerpt} /></blockquote>;
  return (
    <div className="table-row-preview">
      <table>
        <tbody>
          {cells.map((cell, index) => (
            <tr key={`${cell.label}-${index}`}>
              <th scope="row"><HighlightText query={query} text={cell.label} /></th>
              <td><HighlightText query={query} text={cell.value || "—"} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SearchResults(props: Props) {
  const { t } = useI18n();
  if (props.error) return <section className="search-empty error"><h2>{t("search.failed")}</h2><p>{props.error}</p>{props.error === SERVICE_UNAVAILABLE_MESSAGE ? <ServiceStartRequest /> : null}</section>;
  if (props.loading && !props.results.length) return <section className="search-empty"><span className="search-pulse" /><h2>{t("search.searching")}</h2><p>{t("search.progress")}</p></section>;
  if (!props.searched) return <section className="search-empty"><span className="search-compass">⌕</span><h2>{t("search.prompt")}</h2><p>{t("search.promptText")}</p></section>;
  if (!props.results.length) return <section className="search-empty"><h2>{t("search.none")}</h2><p>{t("search.noneText")}</p></section>;
  return (
    <section className="result-list">
      <header><p><strong>{props.results.length}</strong> results</p><span>{t("search.sorted")}</span></header>
      {props.results.map((result) => {
        const evidence = result.evidence;
        const location = evidence.row ? `Row ${evidence.row}` : evidence.line_start ? `Lines ${evidence.line_start}–${evidence.line_end || evidence.line_start}` : "Data card";
        return (
          <article className="result-card" key={`${result.rank}-${evidence.node_id}-${evidence.line_start}`}>
            <div className="result-rank">{String(result.rank).padStart(2, "0")}</div>
            <div className="result-content">
              <div className="result-meta"><span className={`kind-badge kind-${evidence.kind}`}>{evidence.kind}</span><span>{evidence.unit_type.replace("_", " ")}</span><span>{location}</span></div>
              <h2><HighlightText query={props.query} text={evidence.title} /></h2>
              <p className="result-path">{props.collection} / {evidence.path}</p>
              <EvidencePreview evidence={evidence} query={props.query} />
              <div className="result-footer"><span>score {result.score.toFixed(3)} · {result.channels.join(" + ")}</span><a href={exploreHref(props.collection, evidence.node_id, evidence.line_start)}>{t("search.open")}</a></div>
            </div>
          </article>
        );
      })}
      {props.nextCursor ? <button className="load-more" disabled={props.loading} onClick={props.onMore} type="button">{props.loading ? t("search.moreLoading") : t("search.more")}</button> : null}
    </section>
  );
}
