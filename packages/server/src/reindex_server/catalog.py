from __future__ import annotations

from threading import RLock

from reindex_server.domain import Collection


class Catalog:
    """Thread-safe development catalog; the PostgreSQL schema mirrors these records."""

    def __init__(self) -> None:
        self._items: dict[str, Collection] = {}
        self._lock = RLock()

    def create(self, collection: Collection) -> Collection:
        with self._lock:
            if collection.id in self._items:
                raise ValueError("collection already exists")
            self._items[collection.id] = collection
            return collection

    def get(self, collection_id: str) -> Collection:
        with self._lock:
            try:
                return self._items[collection_id]
            except KeyError as error:
                raise KeyError("collection not found") from error
