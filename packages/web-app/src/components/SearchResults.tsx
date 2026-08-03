import { exploreHref } from "../route";
import type { SearchEvidence, SearchResult } from "../types";

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
  if (props.error) return <section className="search-empty error"><h2>搜索失败</h2><p>{props.error}</p></section>;
  if (props.loading && !props.results.length) return <section className="search-empty"><span className="search-pulse" /><h2>正在搜索</h2><p>正在组合匹配的 Evidence。</p></section>;
  if (!props.searched) return <section className="search-empty"><span className="search-compass">⌕</span><h2>搜索可信证据</h2><p>选择 Collection，输入问题，然后从数据卡、正文和表格行中查找结果。</p></section>;
  if (!props.results.length) return <section className="search-empty"><h2>没有找到结果</h2><p>尝试更短的关键词、其他模式或移除 Node 类型筛选。</p></section>;
  return (
    <section className="result-list">
      <header><p><strong>{props.results.length}</strong> results</p><span>按相关性排序</span></header>
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
              <div className="result-footer"><span>score {result.score.toFixed(3)} · {result.channels.join(" + ")}</span><a href={exploreHref(props.collection, evidence.node_id, evidence.line_start)}>在 Explore 中打开 →</a></div>
            </div>
          </article>
        );
      })}
      {props.nextCursor ? <button className="load-more" disabled={props.loading} onClick={props.onMore} type="button">{props.loading ? "加载中…" : "加载更多结果"}</button> : null}
    </section>
  );
}
