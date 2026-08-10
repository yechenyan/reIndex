# ReIndex Wiki

## Reference

- [`reference/reindex-v1.0-standard.md`](reference/reindex-v1.0-standard.md): current package protocol
- [`reference/reindex-input-v1.0.md`](reference/reindex-input-v1.0.md): optional raw `reIndex.md` authoring protocol
- [`reference/http-api.md`](reference/http-api.md): current HTTP API semantics and workflow
- [`reindex-http-v1.yaml`](../packages/server/src/reindex_server/openapi/reindex-http-v1.yaml): authoritative HTTP v1 OpenAPI contract

## User guides

- [`overview.md`](overview.md): product intent and workflow
- [`user/quickstart.md`](user/quickstart.md): current local commands and fixture
- [`user/pdf-table-codegen.md`](user/pdf-table-codegen.md): let an Agent generate reusable PDF table extraction code
- [`user/pdf-extractor-pdf.md`](user/pdf-extractor-pdf.md): coarse discovery and one-table Extraction/QA workflow
- [`user/pdf-to-markdown.md`](user/pdf-to-markdown.md): LiteParse-first PDF conversion with verified table fallback
- [`user/start-local-service.md`](user/start-local-service.md): start ParadeDB and the local API with embeddings enabled

## Developer guides

- [`dev/architecture.md`](dev/architecture.md): workspace and package boundaries
- [`dev/backend-service.md`](dev/backend-service.md): PostgreSQL storage, indexing, and HTTP API design
- [`dev/setup.md`](dev/setup.md): uv-based setup and checks
- [`dev/testing.md`](dev/testing.md): unit, integration, and real HTTP E2E testing
- [`dev/release.md`](dev/release.md): Python package, CLI artifact verification, and PyPI release
- [`dev/deploy.md`](dev/deploy.md): Render Blueprint baseline
- [`dev/tasks.md`](dev/tasks.md): task notes, human review, and archival
