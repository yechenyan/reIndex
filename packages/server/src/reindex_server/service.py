from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid5

from reindex_server.domain import (
    Collection,
    Node,
    NodeResource,
    Resource,
    SearchHit,
    SearchOptions,
    SearchResponse,
    safe_relative_path,
)
from reindex_server.embeddings import EmbeddingProvider
from reindex_server.errors import ConflictError
from reindex_server.node_parser import PackageError, parse_node_card
from reindex_server.package_import import load_package, unpack_archive
from reindex_server.pagination import paginate_hits
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

    def create_collection(self, content: bytes) -> Collection:
        card = parse_node_card(content, "index.node.md")
        metadata = card.metadata
        if metadata["kind"] != "group" or "order" in metadata:
            raise PackageError("Collection root must be an unordered group Node")
        if any(key in metadata for key in ("source", "content", "assets")):
            raise PackageError("Collection root cannot reference files during creation")
        collection_id = str(metadata["id"])
        stored = self.store.put_bytes(card.content)
        resource = Resource(
            str(uuid5(UUID(collection_id), "package:index.node.md")),
            collection_id,
            "package",
            "index.node.md",
            "index.node.md",
            stored.sha256,
            stored.byte_size,
            "text/markdown",
            stored.object_key,
        )
        node_hash = hashlib.sha256(card.content).hexdigest()
        root = Node(
            collection_id,
            collection_id,
            "index.node.md",
            None,
            None,
            (collection_id,),
            (),
            "group",
            metadata["title"],
            metadata["description"],
            card.markdown,
            {},
            node_hash,
            [NodeResource("card", 0, resource)],
        )
        collection = Collection(collection_id, metadata["title"])
        collection.nodes[root.id] = root
        collection.resources[("package", "index.node.md")] = resource
        return self.catalog.create(collection)

    async def upload_raw(self, collection_id: str, raw_path: str, upload) -> dict:
        collection = self.catalog.get(collection_id)
        logical_path = safe_relative_path(raw_path).as_posix()
        with tempfile.NamedTemporaryFile(prefix="reindex-upload-") as stream:
            while chunk := await upload.read(1024 * 1024):
                stream.write(chunk)
            stream.flush()
            stored = self.store.put_file(Path(stream.name))
        existing = collection.resources.get(("raw", logical_path))
        if existing and existing.sha256 != stored.sha256:
            raise ConflictError("raw path already exists with different content")
        resource = existing or Resource(
            str(uuid5(UUID(collection_id), f"raw:{logical_path}")),
            collection_id,
            "raw",
            logical_path,
            upload.filename or Path(logical_path).name,
            stored.sha256,
            stored.byte_size,
            upload.content_type or "application/octet-stream",
            stored.object_key,
        )
        self.catalog.remember_resource(resource)
        return {
            "collection_id": collection_id,
            "resource_id": resource.id,
            "raw_path": logical_path,
            "sha256": resource.sha256,
        }

    def queue_import(self, collection_id: str) -> None:
        collection = self.catalog.get(collection_id)
        if collection.status in {"queued", "validating", "indexing"}:
            raise ConflictError("Collection import already in progress")
        collection.status = "queued"
        collection.error = None
        collection.progress = {"stage": "queued"}
        self.catalog.sync(collection)

    def import_bytes(self, collection_id: str, archive_bytes: bytes) -> None:
        collection = self.catalog.get(collection_id)
        collection.status = "validating"
        collection.progress = {"stage": "validating"}
        self.catalog.sync(collection)
        try:
            with tempfile.TemporaryDirectory(prefix="reindex-import-") as directory:
                archive = Path(directory) / "package.zip"
                archive.write_bytes(archive_bytes)
                unpacked = Path(directory) / "unpacked"
                unpacked.mkdir()
                unpack_archive(archive, unpacked)
                snapshot = load_package(
                    unpacked, collection_id, self.store, collection.resources
                )
            collection.status = "indexing"
            collection.progress = {
                "stage": "indexing",
                "search_units": len(snapshot.units),
            }
            self.catalog.sync(collection)
            profile = None
            if self.embeddings.name != "disabled":
                vectors = self.embeddings.embed_documents(
                    unit.contextual_text for unit in snapshot.units
                )
                for unit, vector in zip(snapshot.units, vectors, strict=True):
                    unit.embedding = vector
                profile = self.embeddings.name
            self.catalog.replace_current(
                collection,
                name=snapshot.name,
                nodes=snapshot.nodes,
                resources=snapshot.resources,
                units=snapshot.units,
                embedding_profile=profile,
                package_hash=snapshot.package_hash,
            )
        except Exception as error:  # noqa: BLE001 - persist every background failure
            collection.status = "failed"
            collection.error = {"code": type(error).__name__, "message": str(error)}
            collection.progress = {"stage": "failed"}
            self.catalog.sync(collection)

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

    def get_node_resource(
        self, collection_id: str, node_id: str, role: str, ordinal: int = 0
    ) -> NodeResource:
        link = self.get_node(collection_id, node_id).link(role, ordinal)
        if not link:
            raise KeyError(f"Node has no {role} resource")
        return link

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
