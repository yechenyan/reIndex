from __future__ import annotations

import tempfile
from dataclasses import replace
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
from reindex_server.reranking import Reranker
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
        reranked_hits, rerank_latency_ms = self.reranker.rerank(options.query, hits)
        hits = _fuse_reranking(hits, reranked_hits, options, self.reranker)
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
            reranker_profile=(
                self.reranker.name if self.reranker.name != "disabled" else None
            ),
            reranked_count=min(len(hits), self.reranker.candidate_limit),
            rerank_latency_ms=(
                round(rerank_latency_ms, 3)
                if self.reranker.name != "disabled"
                else None
            ),
            rerank_fusion_weight=(
                self.reranker.fusion_weight
                if self.reranker.name != "disabled"
                else None
            ),
            rerank_rrf_k=(options.rrf_k if self.reranker.name != "disabled" else None),
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


def _fuse_reranking(
    hits: list[SearchHit],
    reranked_hits: list[SearchHit],
    options: SearchOptions,
    reranker: Reranker,
) -> list[SearchHit]:
    """Fuse retrieval and cross-encoder ranks without comparing raw model scores."""
    if reranker.name == "disabled" or not hits:
        return hits

    original_position = {hit.unit.id: index for index, hit in enumerate(hits, 1)}
    rerank_position = {
        hit.unit.id: index
        for index, hit in enumerate(reranked_hits, 1)
        if hit.rerank_score is not None
    }
    rerank_score = {
        hit.unit.id: hit.rerank_score
        for hit in reranked_hits
        if hit.rerank_score is not None
    }
    rerank_bonus = _confidence_bonus(reranked_hits)
    fused: list[SearchHit] = []
    for hit in hits:
        ranks = dict(hit.ranks)
        score = 0.0
        lexical_rank = ranks.get("lexical")
        semantic_rank = ranks.get("semantic")
        if lexical_rank is not None:
            score += options.lexical_weight / (options.rrf_k + lexical_rank)
        if semantic_rank is not None:
            score += options.semantic_weight / (options.rrf_k + semantic_rank)
        if not ranks:
            score = 1 / (options.rrf_k + original_position[hit.unit.id])
        if rank := rerank_position.get(hit.unit.id):
            ranks["rerank"] = rank
            score += reranker.fusion_weight / (options.rrf_k + rank)
        bonus = rerank_bonus.get(hit.unit.id, 0.0)
        score += bonus
        fused.append(
            replace(
                hit,
                score=score,
                ranks=ranks,
                rerank_score=rerank_score.get(hit.unit.id),
                rerank_bonus=bonus or None,
            )
        )
    return sorted(
        fused,
        key=lambda hit: (-hit.score, original_position[hit.unit.id], hit.unit.id),
    )


def _confidence_bonus(reranked_hits: list[SearchHit]) -> dict[str, float]:
    """Permit a clearly dominant cross-encoder result to break an RRF deadlock.

    Cross-encoder scores are not comparable between queries, so only the first
    result's positive within-query margin is used.  The cap keeps retrieval
    ranks dominant when the model is uncertain or wrong.
    """
    scored = [hit for hit in reranked_hits if hit.rerank_score is not None]
    if len(scored) < 2:
        return {}
    first, second = scored[:2]
    margin = first.rerank_score - second.rerank_score
    if first.rerank_score <= 0 or margin <= 0.5:
        return {}
    return {first.unit.id: min(0.006, (margin - 0.5) * 0.003)}
