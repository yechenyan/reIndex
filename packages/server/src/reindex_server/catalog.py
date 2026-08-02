from __future__ import annotations

from threading import RLock

from reindex_server.domain import (
    Collection,
    CollectionVersion,
    Node,
    Resource,
    SearchUnit,
)
from reindex_server.errors import ConflictError
from reindex_server.memory_version_catalog import MemoryVersionCatalogMixin


class Catalog(MemoryVersionCatalogMixin):
    """Thread-safe current-state catalog used by tests and local development."""

    def __init__(self) -> None:
        self._items: dict[str, Collection] = {}
        self._versions: dict[str, CollectionVersion] = {}
        self._version_files: dict[str, list[dict]] = {}
        self._embedding_cache: dict[tuple[str, str], list[float]] = {}
        self._lock = RLock()

    def create(self, collection: Collection) -> Collection:
        with self._lock:
            if collection.id in self._items:
                raise ConflictError("collection already exists")
            self._items[collection.id] = collection
            return collection

    def get(self, collection_id: str) -> Collection:
        with self._lock:
            try:
                return self._items[collection_id]
            except KeyError as error:
                raise KeyError("collection not found") from error

    def get_by_name(self, name: str) -> Collection:
        with self._lock:
            for collection in self._items.values():
                if collection.name == name:
                    return collection
        raise KeyError("collection not found")

    def sync(self, collection: Collection) -> None:
        self.get(collection.id)

    def get_node(self, collection_id: str, node_id: str) -> Node:
        collection = self.get(collection_id)
        try:
            return collection.nodes[node_id]
        except KeyError as error:
            raise KeyError("node not found") from error

    def get_node_by_path(self, collection_id: str, path: str) -> Node:
        collection = self.get(collection_id)
        for node in collection.nodes.values():
            if node.path == path:
                return node
        raise KeyError("node not found")

    def browse(
        self, collection_id: str, parent_node_id: str | None, recursive: bool
    ) -> list[Node]:
        collection = self.get(collection_id)
        if not recursive:
            return sorted(
                (
                    node
                    for node in collection.nodes.values()
                    if node.parent_id == parent_node_id
                ),
                key=lambda node: node.order if node.order is not None else -1,
            )
        anchor = parent_node_id or collection_id
        if anchor not in collection.nodes:
            raise KeyError("parent node not found")
        return sorted(
            (
                node
                for node in collection.nodes.values()
                if anchor in node.tree_path
                and (parent_node_id is None or node.id != anchor)
            ),
            key=lambda node: node.order_path,
        )

    def replace_current(
        self,
        collection: Collection,
        *,
        name: str,
        nodes: dict[str, Node],
        resources: dict[tuple[str, str], Resource],
        units: list[SearchUnit],
        embedding_profile: str | None,
        package_hash: str,
    ) -> None:
        with self._lock:
            collection.name = name
            collection.nodes = nodes
            collection.resources = resources
            collection.units = units
            collection.package_hash = package_hash
            collection.embedding_profile = embedding_profile
            collection.status = "ready"
            collection.error = None
            collection.progress = {
                "stage": "ready",
                "nodes": len(nodes),
                "resources": len(resources),
                "search_units": len(units),
                "embedding_profile": embedding_profile,
            }

    def push_current(
        self,
        *,
        collection_id: str,
        name: str,
        nodes: dict[str, Node],
        resources: dict[tuple[str, str], Resource],
        units: list[SearchUnit],
        embedding_profile: str | None,
        package_hash: str,
    ) -> Collection:
        with self._lock:
            for item in self._items.values():
                if item.name == name and item.id != collection_id:
                    raise ConflictError("collection name already exists")
            collection = self._items.get(collection_id) or Collection(
                collection_id, name
            )
            self._items[collection_id] = collection
            self.replace_current(
                collection,
                name=name,
                nodes=nodes,
                resources=resources,
                units=units,
                embedding_profile=embedding_profile,
                package_hash=package_hash,
            )
            return collection
