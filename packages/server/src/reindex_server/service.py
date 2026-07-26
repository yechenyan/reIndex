from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from reindex_server.catalog import Catalog
from reindex_server.domain import (
    Collection,
    Node,
    SearchHit,
    SearchOptions,
    SearchResponse,
)
from reindex_server.embeddings import EmbeddingProvider
from reindex_server.package_import import (
    PackageError,
    load_package,
    parse_node,
    unpack_archive,
)
from reindex_server.pagination import paginate_hits
from reindex_server.storage import FileStore


class SearchBackend(Protocol):
    def search(
        self,
        collection: Collection,
        options: SearchOptions,
        query_embedding: list[float] | None,
    ) -> list[SearchHit]: ...

    def grep(
        self,
        collection: Collection,
        pattern: str,
        limit: int,
        regex: bool,
        case_sensitive: bool,
    ) -> list[SearchHit]: ...


class ReindexService:
    def __init__(
        self,
        catalog: Catalog,
        store: FileStore,
        embeddings: EmbeddingProvider,
        search_backend: SearchBackend | None = None,
    ) -> None:
        self.catalog = catalog
        self.store = store
        self.embeddings = embeddings
        self.search_backend = search_backend

    def create_collection(self, content: str) -> Collection:
        root = parse_node(content, "index.node.md")
        if root.kind != "group":
            raise PackageError("collection root must be a group Node")
        return self.catalog.create(Collection.create(root))

    async def upload_raw(self, collection_id: str, raw_path: str, upload) -> dict:
        collection = self.catalog.get(collection_id)
        sha256, path = await self.store.save_raw(collection_id, raw_path, upload)
        existing = collection.raw.get(raw_path)
        if existing and existing != sha256:
            raise ValueError("raw path already exists with different content")
        collection.raw[raw_path] = sha256
        if hasattr(self.catalog, "remember_raw"):
            self.catalog.remember_raw(collection_id, raw_path, sha256, path)
        return {"collection_id": collection_id, "raw_path": raw_path, "sha256": sha256}

    def queue_import(self, collection_id: str) -> None:
        collection = self.catalog.get(collection_id)
        collection.begin_import()
        self._sync(collection)

    def import_bytes(self, collection_id: str, archive_bytes: bytes) -> None:
        collection = self.catalog.get(collection_id)
        previous_profile = collection.embedding_profile
        revision_id = str(uuid4())
        collection.status = "validating"
        self._sync(collection)
        try:
            with tempfile.TemporaryDirectory(prefix="reindex-import-") as directory:
                archive = Path(directory) / "package.zip"
                archive.write_bytes(archive_bytes)
                unpacked = Path(directory) / "package"
                unpacked.mkdir()
                unpack_archive(archive, unpacked)
                nodes, units = load_package(
                    unpacked, collection_id, self.store, revision_id, collection.raw
                )
            collection.status = "indexing"
            collection.progress = {
                "stage": "full_text",
                "completed": len(units),
                "total": len(units),
            }
            self._sync(collection)
            if self.embeddings.name != "disabled":
                vectors = self.embeddings.embed_documents(
                    unit.contextual_text for unit in units
                )
                for unit, vector in zip(units, vectors, strict=True):
                    unit.embedding = vector
            collection.status = "ready"
            collection.embedding_profile = (
                self.embeddings.name if self.embeddings.name != "disabled" else None
            )
            collection.progress = {
                "stage": "ready",
                "completed": len(units),
                "total": len(units),
                "embedding_profile": collection.embedding_profile,
            }
            if hasattr(self.catalog, "replace_revision"):
                self.catalog.replace_revision(
                    collection,
                    revision_id,
                    nodes,
                    units,
                    collection.embedding_profile,
                )
                collection.active_revision = revision_id
            else:
                collection.active_revision = revision_id
                self._sync(collection)
            collection.nodes, collection.units = nodes, units
        except Exception as error:
            collection.embedding_profile = previous_profile
            collection.status = "failed"
            collection.error = {"code": type(error).__name__, "message": str(error)}
            self._sync(collection)

    def get_node(self, collection_id: str, node_id: str) -> Node:
        collection = self.catalog.get(collection_id)
        try:
            return collection.nodes[node_id]
        except KeyError as error:
            raise KeyError("node not found") from error

    def browse(self, collection_id: str, parent_node_id: str | None) -> list[Node]:
        collection = self.catalog.get(collection_id)
        return [
            node
            for node in collection.nodes.values()
            if node.parent_id == parent_node_id
        ]

    def search(self, collection_id: str, options: SearchOptions) -> SearchResponse:
        collection = self.catalog.get(collection_id)
        if not collection.active_revision:
            raise ValueError("collection is not ready")
        if self.search_backend is None:
            raise RuntimeError("search requires a ParadeDB DATABASE_URL")
        query_embedding = None
        if options.mode in {"semantic", "hybrid"}:
            if self.embeddings.name == "disabled":
                raise RuntimeError(
                    "semantic and hybrid search require REINDEX_EMBEDDINGS=qwen"
                )
            if collection.embedding_profile != self.embeddings.name:
                raise RuntimeError(
                    "active revision embedding profile does not match the query embedding profile"
                )
            query_embedding = self.embeddings.embed_query(options.query)
        hits = self.search_backend.search(collection, options, query_embedding)
        page, offset, candidate_count, next_cursor = paginate_hits(
            hits, options, collection.active_revision
        )
        return SearchResponse(
            executed_mode=options.mode,
            embedding_profile=collection.embedding_profile,
            revision_id=collection.active_revision,
            results=page,
            result_offset=offset,
            candidate_count=candidate_count,
            next_cursor=next_cursor,
        )

    def grep(
        self,
        collection_id: str,
        pattern: str,
        limit: int,
        regex: bool,
        case_sensitive: bool,
    ) -> SearchResponse:
        collection = self.catalog.get(collection_id)
        if not collection.active_revision:
            raise ValueError("collection is not ready")
        if self.search_backend is None:
            raise RuntimeError("grep requires a ParadeDB DATABASE_URL")
        results = self.search_backend.grep(
            collection, pattern, limit, regex, case_sensitive
        )
        return SearchResponse(
            executed_mode="grep",
            embedding_profile=None,
            revision_id=collection.active_revision,
            results=results,
            candidate_count=len(results),
        )

    def _sync(self, collection: Collection) -> None:
        if hasattr(self.catalog, "sync"):
            self.catalog.sync(collection)
