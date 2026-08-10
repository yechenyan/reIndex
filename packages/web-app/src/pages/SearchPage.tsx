import { FormEvent, useEffect, useState } from "react";
import { listCollections, searchNodes } from "../api";
import { SearchResults } from "../components/SearchResults";
import type { CollectionSummary, NodeKind, SearchResult } from "../types";
import { useI18n } from "../i18n";

const kinds: NodeKind[] = ["group", "text", "table", "image", "file"];

export function SearchPage() {
  const { t } = useI18n();
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
      setError(reason instanceof Error ? reason.message : t("search.failed"));
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
        <h1>{t("search.title")}</h1>
        <p>{t("search.description")}</p>
        <form className="search-form" onSubmit={submit}>
          <label>
            <span>Collection</span>
            <select onChange={(event) => setCollection(event.target.value)} value={collection}>
              {collections.map((item) => <option key={item.collection_id} value={item.name}>{item.name}</option>)}
            </select>
          </label>
          <label className="query-field">
            <span className="sr-only">Search query</span>
            <input onChange={(event) => setQuery(event.target.value)} placeholder={t("search.placeholder")} value={query} />
          </label>
          <button disabled={!collection || !query.trim() || loading} type="submit">{loading ? t("search.searching") : t("search.submit")}<i>→</i></button>
        </form>
      </section>
      <section className="search-workspace">
        <aside className="search-filters">
          <div className="filter-heading"><p className="eyebrow">SEARCH SETTINGS</p><button onClick={() => setSelectedKinds([])} type="button">{t("search.reset")}</button></div>
          <fieldset>
            <legend>{t("search.mode")}</legend>
            {(["hybrid", "lexical", "semantic"] as const).map((value) => (
              <label className="radio-row" key={value}><input checked={mode === value} name="mode" onChange={() => setMode(value)} type="radio" /><span><strong>{value}</strong><small>{t(`search.${value}`)}</small></span></label>
            ))}
          </fieldset>
          <fieldset>
            <legend>{t("search.types")}</legend>
            {kinds.map((kind) => (
              <label className="check-row" key={kind}><input checked={selectedKinds.includes(kind)} onChange={() => toggleKind(kind)} type="checkbox" /><span>{kind}</span></label>
            ))}
          </fieldset>
          <div className="scope-note"><span>i</span><p>{t("search.scope")}</p></div>
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
