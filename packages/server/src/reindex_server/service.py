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
    SearchUnit,
    safe_relative_path,
)
from reindex_server.embeddings import EmbeddingProvider
from reindex_server.pagination import paginate_hits
from reindex_server.push_import import prepare_push
from reindex_server.reranking import Reranker
from reindex_server.search_fusion import fuse_reranking
from reindex_server.storage import ObjectStore


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

    def warmup(self) -> None:
        self.embeddings.warmup()
        self.reranker.warmup()

    def resolve_collection(self, name: str) -> Collection:
        return self.catalog.get_by_name(name)

    def push(self, name: str, package_archive: Path, sources_archive: Path) -> dict:
        prepared = prepare_push(name, package_archive, sources_archive, self.store)
        snapshot = prepared.snapshot
        profile = self._embed(snapshot.units)
        collection = self.catalog.push_current(
            collection_id=prepared.collection_id,
            name=prepared.name,
            nodes=snapshot.nodes,
            resources=snapshot.resources,
            units=snapshot.units,
            embedding_profile=profile,
            package_hash=snapshot.package_hash,
        )
        return {
            "status": collection.status,
            "name": collection.name,
            "collection_id": collection.id,
            "package_hash": collection.package_hash,
            "nodes": len(snapshot.nodes),
            "sources": prepared.source_count,
            "resources": len(snapshot.resources),
            "search_units": len(snapshot.units),
            "embedding_profile": profile,
        }

    def pull(self, name: str) -> tuple[bytes, Collection]:
        collection = self.resolve_collection(name)
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
        return output.getvalue(), collection

    def get_node_by_path(self, collection_id: str, path: str) -> Node:
        return self.catalog.get_node_by_path(collection_id, path)

    def _embed(self, units: list[SearchUnit]) -> str | None:
        if self.embeddings.name == "disabled":
            return None
        vectors = self.embeddings.embed_documents(
            unit.contextual_text for unit in units
        )
        for unit, vector in zip(units, vectors, strict=True):
            unit.embedding = vector
        return self.embeddings.name

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
