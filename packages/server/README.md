# reindex-server

Backend HTTP service for ReIndex storage and query APIs.

```bash
uv run reindex-server run
```

The service implements the fixed action endpoints documented in
[`wiki/dev/backend-service.md`](../../wiki/dev/backend-service.md): create a
collection root, upload raw files by relative path, import a ReIndex zip archive,
check collection state, search, browse/read/download Nodes, and query CSV tables.

For local development, bytes are stored under `.reindex-data/` and the catalog is
process-local. Set `REINDEX_DATA_DIR` to choose a different local directory.

Install the PostgreSQL serving schema (including `vector`, `pg_trgm`, and
`unaccent`) with a database URL whose server supports those extensions:

```bash
DATABASE_URL=postgresql://... uv run reindex-server init-db
```

Semantic search uses the local `Qwen/Qwen3-Embedding-0.6B` profile when
`REINDEX_EMBEDDINGS=qwen` and the optional dependency is installed:

```bash
uv sync --extra embeddings
REINDEX_EMBEDDINGS=qwen uv run reindex-server run
```

Without that setting, lexical search remains available and semantic requests
return a configuration error rather than silently using a remote model.
