import { FormEvent, useEffect, useState } from "react";
import { listCollections, searchNodes } from "../api";
import { SearchResults } from "../components/SearchResults";
import { defaultSearchSettings, SearchOptionsPanel, type SearchSettings } from "../components/SearchOptionsPanel";
import type { CollectionSummary, SearchResult } from "../types";
import { useI18n } from "../i18n";

export function SearchPage() {
  const { t } = useI18n();
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [collection, setCollection] = useState("");
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [settings, setSettings] = useState<SearchSettings>(defaultSearchSettings);
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

  async function runSearch(cursor?: string, append = false) {
    const activeQuery = append ? submittedQuery : query.trim();
    if (!collection || !activeQuery) return;
    if (!append) setSubmittedQuery(activeQuery);
    setLoading(true);
    setError("");
    try {
      const response = await searchNodes({ collection, query: activeQuery, mode: settings.mode, limit: settings.limit, candidateLimit: settings.candidateLimit, nodeIds: settings.nodeIds.split(",").map((value) => value.trim()).filter(Boolean), kinds: settings.kinds, pathPrefix: settings.pathPrefix || undefined, subtreeNodeId: settings.subtreeNodeId || undefined, lexicalWeight: settings.lexicalWeight, semanticWeight: settings.semanticWeight, rrfK: settings.rrfK, maxPerNode: settings.maxPerNode, semanticThreshold: settings.semanticThreshold === "" ? undefined : Number(settings.semanticThreshold), cursor });
      setResults((current) => append ? [...current, ...response.results] : response.results);
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
    void runSearch(settings.cursor || undefined);
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
        <SearchOptionsPanel settings={settings} setSettings={setSettings} />
        <SearchResults
          collection={collection}
          error={error}
          loading={loading}
          nextCursor={nextCursor}
          onMore={() => nextCursor && void runSearch(nextCursor, true)}
          query={submittedQuery}
          results={results}
          searched={searched}
        />
      </section>
    </div>
  );
}
