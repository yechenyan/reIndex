# reindex-server

Backend HTTP service for ReIndex storage and query APIs.

```bash
uv run reindex-server run
```

The service implements the fixed action endpoints documented in
[`wiki/dev/backend-service.md`](../../wiki/dev/backend-service.md): create a
collection root, upload raw files by relative path, import a ReIndex zip archive,
check collection state, search, browse/read/download Nodes, and query CSV tables.

For local development, bytes are stored under `.reindex-data/`. Set
`REINDEX_DATA_DIR` to choose a different local directory. Search has no
process-local fallback: a ParadeDB connection is required.

Start ParadeDB 0.24.3+ and install the serving schema, including `pg_search`
BM25 and `pgvector` HNSW indexes:

```bash
DATABASE_URL=postgresql://... uv run reindex-server init-db
```

The API accepts `DATABASE_URL` or the discrete `PARADEDB_HOST`,
`PARADEDB_PORT`, `PARADEDB_USER`, `PARADEDB_PASSWORD`, and
`PARADEDB_DATABASE` settings. Imports persist immutable revisions, contextual
chunks and Qwen embeddings. Search runs only against the active revision and
its embedding profile. Catalog and search share a bounded connection pool;
tune it with `REINDEX_DB_POOL_MIN` (default `1`), `REINDEX_DB_POOL_MAX`
(default `10`) and `REINDEX_DB_POOL_TIMEOUT` in seconds (default `5`).

```bash
DATABASE_URL=postgresql://... REINDEX_EMBEDDINGS=qwen uv run reindex-server run
```

Install the embedding runtime for semantic and hybrid search:

```bash
uv sync --extra embeddings
REINDEX_EMBEDDINGS=qwen uv run reindex-server run
```

`POST /v1/search` defaults to hybrid retrieval. ParadeDB performs boosted,
multi-field BM25; pgvector performs cosine ANN; PostgreSQL combines both
candidate lists using configurable weighted RRF. The service then uses the
multilingual `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` reranker to assess
the leading 20 candidates, regardless of query language or result kind. The
final order fuses lexical, semantic and reranker ranks with weighted RRF: the
reranker is an added signal, not a replacement for retrieval. A capped bonus
applies only to a clearly dominant, positive cross-encoder top result. The API
exposes the original channel scores, rerank score, applied bonus and latency.
`lexical` remains usable without the embedding model, but `semantic` and
`hybrid` never silently fall back.

Reranking defaults to `minilm`. It uses the `embeddings` optional dependency
and is warmed before the service becomes ready. Set `REINDEX_RERANKER=disabled`
to bypass the second stage. Tune the bounded second-stage work with
`REINDEX_RERANK_LIMIT` (default `20`, range `1..100`),
`REINDEX_RERANK_BATCH_SIZE` (default `8`), `REINDEX_RERANK_MAX_LENGTH`
(default `512`, range `64..512`) and `REINDEX_RERANK_WEIGHT` (default `0.75`,
range `0..10`).

Interactive OpenAPI documentation is available at `/docs`, and the machine
readable schema is available at `/openapi.json`. Request models reject unknown
fields and validate collection/Node IDs as UUIDs, so misspelled parameters do
not silently change retrieval behavior.

```json
{
  "collection_id": "056e95b3-aad8-4740-af7e-973356ec4e44",
  "query": "未来光伏装机容量是多少？",
  "mode": "hybrid",
  "limit": 10,
  "candidate_limit": 100,
  "cursor": null,
  "filters": {
    "kinds": ["text", "table"],
    "path_prefix": "reports/"
  },
  "ranking": {
    "lexical_weight": 0.5,
    "semantic_weight": 1.0,
    "rrf_k": 60,
    "max_per_node": 3,
    "semantic_threshold": 0.25
  }
}
```

The response is a typed contract. With reranking enabled, `score` is the final
rank-fusion score, not a cross-encoder probability. BM25, cosine,
cross-encoder and any capped confidence bonus remain under `scores`.

```json
{
  "executed_mode": "hybrid",
  "embedding_profile": "Qwen/Qwen3-Embedding-0.6B@1024",
  "revision_id": "e963d745-d8ef-4ec3-bb57-b23406618239",
  "candidate_count": 12,
  "next_cursor": null,
  "results": [
    {
      "rank": 1,
      "score": 0.0245,
      "channels": ["lexical", "semantic"],
      "ranks": {"lexical": 2, "semantic": 1, "rerank": 1},
      "scores": {"bm25": 14.2, "semantic": 0.4787, "rerank": 7.48, "rerank_bonus": 0.0046},
      "evidence": {
        "node_id": "f1592bf6-c0bc-4bba-9296-ae9aead4c660",
        "path": "reports/plan.node.md",
        "kind": "text",
        "title": "C. Planungsgrundlagen",
        "description": "Lastentwicklung und dezentrale Erzeugung.",
        "parent_id": null,
        "locator": {"pages": [6, 6]},
        "excerpt": "In Summe halten wir ... von 70 MW auf 160 MW ...",
        "source_sha256": null,
        "row": null,
        "line_start": 31,
        "line_end": 31,
        "chunk_ordinal": 5
      }
    }
  ],
  "applied": {
    "candidate_limit": 100,
    "filters": {"node_ids": [], "kinds": [], "path_prefix": null},
    "ranking": {
      "lexical_weight": 0.5,
      "semantic_weight": 1.0,
      "rrf_k": 60,
      "max_per_node": 3,
      "semantic_threshold": null
    }
  },
  "reranking": {
    "profile": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
    "candidate_limit": 20,
    "reranked_count": 20,
    "latency_ms": 242.1,
    "fusion": "weighted_rrf",
    "weight": 0.75,
    "rrf_k": 60
  }
}
```

When more diversified candidates remain, the response contains `next_cursor`.
Send it back unchanged with the same query, filters, ranking settings and active
revision. Results retain global ranks across pages. A changed query or revision
invalidates the cursor.

Every HTTP response includes `X-Request-ID`. Clients may supply an ID containing
letters, digits, `.`, `_`, `:`, or `-` (maximum 128 characters); otherwise the
server generates one. JSON errors use one envelope:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "invalid search cursor for this query or active revision",
    "request_id": "agent-search-42"
  }
}
```

The stable error classes are `invalid_request` (`400` or schema-level `422`),
`not_found` (`404`), `conflict` (`409`), and `internal_error` (`500`).
Validation errors also contain a `details` array.

Archive parsing, embedding and revision writes run as a background thread task.
During a replacement import, the previous active revision keeps serving until
the new revision is ready and switches atomically. The embedding model is
warmed during application startup, so its one-time load does not penalize the
first search request.

`POST /v1/reindex/import` remains collection-scoped and returns
`{"collection_id": "...", "status": "queued"}`. Poll
`POST /v1/collections/status` for progress. It does not yet return a durable job
ID: the current thread task survives normal requests but not an API process
crash.

Run repeatable lexical/semantic/hybrid quality and latency evaluation:

```bash
DATABASE_URL=postgresql://... REINDEX_EMBEDDINGS=qwen \
  uv run reindex-server eval-search \
  --collection-id 056e95b3-aad8-4740-af7e-973356ec4e44 \
  --dataset testbase/test1/search-eval.jsonl \
  --mode all --cutoffs 5,10
```

Each JSONL row contains `query` and one or both of `relevant_node_ids` and
`relevant_unit_ids`. The report includes Recall, MRR, NDCG, mean latency, P50
and P95. Use these measurements to tune rerank candidate count, chunking and
query rewrite profiles.
