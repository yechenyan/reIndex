from __future__ import annotations

import math
import tempfile
from pathlib import Path
from uuid import uuid4

from reindex_server.catalog import Catalog
from reindex_server.domain import Collection, Node, SearchUnit
from reindex_server.embeddings import EmbeddingProvider
from reindex_server.package_import import PackageError, load_package, parse_node, unpack_archive
from reindex_server.storage import FileStore


class ReindexService:
    def __init__(self, catalog: Catalog, store: FileStore, embeddings: EmbeddingProvider) -> None:
        self.catalog, self.store, self.embeddings = catalog, store, embeddings

    def create_collection(self, content: str) -> Collection:
        root = parse_node(content, "index.node.md")
        if root.kind != "group":
            raise PackageError("collection root must be a group Node")
        return self.catalog.create(Collection.create(root))

    async def upload_raw(self, collection_id: str, raw_path: str, upload) -> dict:
        collection = self.catalog.get(collection_id)
        sha256, _ = await self.store.save_raw(collection_id, raw_path, upload)
        existing = collection.raw.get(raw_path)
        if existing and existing != sha256:
            raise ValueError("raw path already exists with different content")
        collection.raw[raw_path] = sha256
        return {"collection_id": collection_id, "raw_path": raw_path, "sha256": sha256}

    def queue_import(self, collection_id: str) -> None:
        collection = self.catalog.get(collection_id)
        collection.begin_import()

    async def import_bytes(self, collection_id: str, archive_bytes: bytes) -> None:
        collection = self.catalog.get(collection_id)
        revision_id = str(uuid4())
        collection.status = "validating"
        try:
            with tempfile.TemporaryDirectory(prefix="reindex-import-") as directory:
                archive = Path(directory) / "package.zip"
                archive.write_bytes(archive_bytes)
                unpacked = Path(directory) / "package"
                unpacked.mkdir()
                unpack_archive(archive, unpacked)
                nodes, units = load_package(unpacked, collection_id, self.store, revision_id, collection.raw)
            collection.status = "indexing"
            collection.progress = {"stage": "full_text", "completed": len(units), "total": len(units)}
            if self.embeddings.name != "disabled":
                vectors = self.embeddings.embed_documents(unit.text for unit in units)
                for unit, vector in zip(units, vectors, strict=True):
                    unit.embedding = vector
            collection.nodes, collection.units = nodes, units
            collection.active_revision, collection.status = revision_id, "ready"
            collection.progress = {"stage": "ready", "completed": len(units), "total": len(units), "embedding_profile": self.embeddings.name}
        except Exception as error:
            collection.status = "failed"
            collection.error = {"code": type(error).__name__, "message": str(error)}

    def get_node(self, collection_id: str, node_id: str) -> Node:
        collection = self.catalog.get(collection_id)
        try:
            return collection.nodes[node_id]
        except KeyError as error:
            raise KeyError("node not found") from error

    def browse(self, collection_id: str, parent_node_id: str | None) -> list[Node]:
        collection = self.catalog.get(collection_id)
        return [node for node in collection.nodes.values() if node.parent_id == parent_node_id]

    def search(self, collection_id: str, query: str, mode: str, limit: int) -> tuple[str, list[tuple[SearchUnit, float]]]:
        collection = self.catalog.get(collection_id)
        if collection.status != "ready":
            raise ValueError("collection is not ready")
        if mode == "semantic":
            if self.embeddings.name == "disabled":
                raise RuntimeError("semantic search requires REINDEX_EMBEDDINGS=qwen")
            query_vector = self.embeddings.embed_query(query)
            results = [(unit, _cosine(query_vector, unit.embedding or [])) for unit in collection.units]
            return mode, sorted(results, key=lambda item: item[1], reverse=True)[:limit]
        normalized = query.casefold()
        results = [(unit, _lexical_score(normalized, unit.text)) for unit in collection.units]
        results = [(unit, score) for unit, score in results if score]
        return "lexical" if mode == "auto" or self.embeddings.name == "disabled" else mode, sorted(results, key=lambda item: item[1], reverse=True)[:limit]


def _lexical_score(query: str, text: str) -> float:
    return float(text.casefold().count(query))


def _cosine(left: list[float], right: list[float]) -> float:
    if not right:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / math.sqrt(sum(a * a for a in right))
