from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Protocol

from reindex_server.domain import (
    Collection,
    Node,
    Resource,
    SearchHit,
    SearchOptions,
    SearchResponse,
    safe_relative_path,
)
from reindex_server.embeddings import EmbeddingProvider
from reindex_server.pagination import paginate_hits
from reindex_server.publication import PublicationManager
from reindex_server.push_protocol import load_snapshot_from_manifest
from reindex_server.reranking import Reranker
from reindex_server.search_fusion import fuse_reranking
from reindex_server.storage import ObjectStore, object_key


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
        catalog,
        store: ObjectStore,
        embeddings: EmbeddingProvider,
        search_backend: SearchBackend | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self.catalog = catalog
        self.store = store
        self.embeddings = embeddings
        self.search_backend = search_backend
        self.reranker = reranker or Reranker()
        self.publications = PublicationManager(catalog, store, embeddings)

    def warmup(self) -> None:
        self.embeddings.warmup()
        self.reranker.warmup()

    def resolve_collection(self, name: str) -> Collection:
        return self.catalog.get_by_name(name)

    def start_push(self, request) -> dict:
        return self.publications.start(request)

    def upload_blob(self, upload_id: str, sha256: str, path: Path) -> dict:
        return self.publications.upload_blob(upload_id, sha256, path)

    def commit_push(self, upload_id: str) -> dict:
        return self.publications.commit(upload_id)

    def fetch_version(self, name: str, version_id: str | None = None) -> dict:
        return self.publications.fetch(name, version_id)

    def history(self, name: str, limit: int, cursor: str | None) -> dict:
        return self.publications.history(name, limit, cursor)

    def pull(
        self, name: str, version_id: str | None = None
    ) -> tuple[bytes, Collection, str, str]:
        collection = self.resolve_collection(name)
        if version_id:
            fetched = self.fetch_version(name, version_id)
            output = io.BytesIO()
            with zipfile.ZipFile(
                output, "w", compression=zipfile.ZIP_DEFLATED
            ) as bundle:
                for item in fetched["manifest"]["files"]:
                    if item["namespace"] != "package" or not item[
                        "logical_path"
                    ].endswith(".node.md"):
                        continue
                    with self.store.open(object_key(item["sha256"])) as stream:
                        bundle.writestr(item["logical_path"], stream.read())
            return (
                output.getvalue(),
                collection,
                fetched["version"]["version_id"],
                fetched["version"]["package_hash"],
            )
        nodes = self.browse(collection.id, None, recursive=True)
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for summary in sorted(nodes, key=lambda value: value.path):
                node = self.get_node(collection.id, summary.id)
                card = node.link("card")
                if card is None:
                    raise KeyError(f"Node has no card resource: {node.path}")
                with self.store.open(card.resource.object_key) as stream:
                    bundle.writestr(node.path, stream.read())
        return (
            output.getvalue(),
            collection,
            collection.active_version_id or "",
            collection.package_hash or "",
        )

    def version_snapshot(self, name: str, version_id: str):
        fetched = self.fetch_version(name, version_id)
        return load_snapshot_from_manifest(
            fetched["manifest"], fetched["collection_id"], self.store
        )

    def get_node_by_path(self, collection_id: str, path: str) -> Node:
        return self.catalog.get_node_by_path(collection_id, path)

    def get_node(self, collection_id: str, node_id: str) -> Node:
        return self.catalog.get_node(collection_id, node_id)

    def browse(
        self, collection_id: str, parent_node_id: str | None, recursive: bool = False
    ) -> list[Node]:
        return self.catalog.browse(collection_id, parent_node_id, recursive)

    def get_raw(self, collection_id: str, raw_path: str) -> Resource:
        collection = self.catalog.get(collection_id)
        try:
            return collection.resources[
                ("raw", safe_relative_path(raw_path).as_posix())
            ]
        except KeyError as error:
            raise KeyError("raw resource not found") from error

    def search(self, collection_id: str, options: SearchOptions) -> SearchResponse:
        collection = self._ready(collection_id)
        if self.search_backend is None:
            raise RuntimeError("search requires a ParadeDB DATABASE_URL")
        query_embedding = None
        if options.mode in {"semantic", "hybrid"}:
            if (
                self.embeddings.name == "disabled"
                or collection.embedding_profile != self.embeddings.name
            ):
                raise RuntimeError(
                    "semantic search requires the Collection embedding profile"
                )
            query_embedding = self.embeddings.embed_query(options.query)
        hits = self.search_backend.search(collection, options, query_embedding)
        reranked, latency = self.reranker.rerank(options.query, hits)
        hits = fuse_reranking(hits, reranked, options, self.reranker)
        page, offset, count, cursor = paginate_hits(
            hits, options, collection.package_hash or ""
        )
        return SearchResponse(
            options.mode,
            collection.embedding_profile,
            page,
            offset,
            count,
            cursor,
            self.reranker.name if self.reranker.name != "disabled" else None,
            min(len(hits), self.reranker.candidate_limit),
            round(latency, 3) if self.reranker.name != "disabled" else None,
            self.reranker.fusion_weight if self.reranker.name != "disabled" else None,
            options.rrf_k if self.reranker.name != "disabled" else None,
        )

    def grep(
        self,
        collection_id: str,
        pattern: str,
        limit: int,
        regex: bool,
        case_sensitive: bool,
    ) -> SearchResponse:
        collection = self._ready(collection_id)
        if self.search_backend is None:
            raise RuntimeError("grep requires a ParadeDB DATABASE_URL")
        results = self.search_backend.grep(
            collection, pattern, limit, regex, case_sensitive
        )
        return SearchResponse("grep", None, results, candidate_count=len(results))

    def _ready(self, collection_id: str) -> Collection:
        collection = self.catalog.get(collection_id)
        if not collection.package_hash:
            raise ValueError("Collection is not ready")
        return collection
