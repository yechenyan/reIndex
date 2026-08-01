from __future__ import annotations

from threading import RLock

from reindex_server.domain import Collection, Node, Resource, SearchUnit
from reindex_server.errors import ConflictError


class Catalog:
    """Thread-safe current-state catalog used by tests and local development."""

    def __init__(self) -> None:
        self._items: dict[str, Collection] = {}
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

    def sync(self, collection: Collection) -> None:
        self.get(collection.id)

    def get_node(self, collection_id: str, node_id: str) -> Node:
        collection = self.get(collection_id)
        try:
            return collection.nodes[node_id]
        except KeyError as error:
            raise KeyError("node not found") from error

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

    def remember_resource(self, resource: Resource) -> None:
        collection = self.get(resource.collection_id)
        collection.resources[(resource.namespace, resource.logical_path)] = resource

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
