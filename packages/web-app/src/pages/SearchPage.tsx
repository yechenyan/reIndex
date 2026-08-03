import { FormEvent, useEffect, useState } from "react";
import { listCollections, searchNodes } from "../api";
import { SearchResults } from "../components/SearchResults";
import type { CollectionSummary, NodeKind, SearchResult } from "../types";

const kinds: NodeKind[] = ["group", "text", "table", "image", "file"];

export function SearchPage() {
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [collection, setCollection] = useState("");
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [mode, setMode] = useState<"lexical" | "semantic" | "hybrid">("hybrid");
  const [selectedKinds, setSelectedKinds] = useState<NodeKind[]>([]);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    listCollections()
      .then((items) => {
        setCollections(items);
        setCollection(items[0]?.name || "");
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  function toggleKind(kind: NodeKind) {
    setSelectedKinds((current) => current.includes(kind) ? current.filter((value) => value !== kind) : [...current, kind]);
  }

  async function runSearch(cursor?: string) {
    const activeQuery = cursor ? submittedQuery : query.trim();
    if (!collection || !activeQuery) return;
    if (!cursor) setSubmittedQuery(activeQuery);
    setLoading(true);
    setError("");
    try {
      const response = await searchNodes({ collection, query: activeQuery, mode, kinds: selectedKinds, cursor });
      setResults((current) => cursor ? [...current, ...response.results] : response.results);
      setNextCursor(response.next_cursor);
      setSearched(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "搜索失败");
      setSearched(true);
    } finally {
      setLoading(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setResults([]);
    setNextCursor(null);
    void runSearch();
  }

  return (
    <div className="search-page">
      <section className="search-hero">
        <p className="eyebrow">REINDEX SEARCH</p>
        <h1>从真实来源中找到答案。</h1>
        <p>搜索数据卡、正文与表格行，并直接回到对应 Node。</p>
        <form className="search-form" onSubmit={submit}>
          <label>
            <span>Collection</span>
            <select onChange={(event) => setCollection(event.target.value)} value={collection}>
              {collections.map((item) => <option key={item.collection_id} value={item.name}>{item.name}</option>)}
            </select>
          </label>
          <label className="query-field">
            <span className="sr-only">搜索内容</span>
            <input onChange={(event) => setQuery(event.target.value)} placeholder="例如：未来十年的电网投资计划是什么？" value={query} />
          </label>
          <button disabled={!collection || !query.trim() || loading} type="submit">{loading ? "搜索中" : "搜索"}<i>→</i></button>
        </form>
      </section>
      <section className="search-workspace">
        <aside className="search-filters">
          <div className="filter-heading"><p className="eyebrow">SEARCH SETTINGS</p><button onClick={() => setSelectedKinds([])} type="button">重置</button></div>
          <fieldset>
            <legend>搜索模式</legend>
            {(["hybrid", "lexical", "semantic"] as const).map((value) => (
              <label className="radio-row" key={value}><input checked={mode === value} name="mode" onChange={() => setMode(value)} type="radio" /><span><strong>{value}</strong><small>{value === "hybrid" ? "全文与语义融合" : value === "lexical" ? "精确关键词匹配" : "自然语言相似度"}</small></span></label>
            ))}
          </fieldset>
          <fieldset>
            <legend>Node 类型</legend>
            {kinds.map((kind) => (
              <label className="check-row" key={kind}><input checked={selectedKinds.includes(kind)} onChange={() => toggleKind(kind)} type="checkbox" /><span>{kind}</span></label>
            ))}
          </fieldset>
          <div className="scope-note"><span>i</span><p>搜索范围是一个 Collection，结果始终读取 active version。</p></div>
        </aside>
        <SearchResults
          collection={collection}
          error={error}
          loading={loading}
          nextCursor={nextCursor}
          onMore={() => nextCursor && void runSearch(nextCursor)}
          query={submittedQuery}
          results={results}
          searched={searched}
        />
      </section>
    </div>
  );
}
