from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from reindex_server.domain import Collection, CollectionVersion
from reindex_server.errors import ConflictError, StaleBaseError
from reindex_server.storage import object_key


class MemoryVersionCatalogMixin:
    def current_version(self, collection_id: str) -> CollectionVersion | None:
        with self._lock:
            collection = self._items.get(collection_id)
            if collection is None or collection.active_version_id is None:
                return None
            return self._versions[collection.active_version_id]

    def get_version(self, collection_id: str, version_id: str) -> CollectionVersion:
        with self._lock:
            try:
                version = self._versions[version_id]
            except KeyError as error:
                raise KeyError("version not found") from error
            if version.collection_id != collection_id:
                raise KeyError("version not found")
            return version

    def list_versions(
        self,
        collection_id: str,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[CollectionVersion]:
        with self._lock:
            self.get(collection_id)
            values = (
                version
                for version in self._versions.values()
                if version.collection_id == collection_id
                and (before is None or version.created_at < before)
            )
            return sorted(
                values, key=lambda value: (value.created_at, value.id), reverse=True
            )[:limit]

    def list_all_versions(self) -> list[CollectionVersion]:
        with self._lock:
            return sorted(
                self._versions.values(),
                key=lambda value: (value.created_at, value.id),
                reverse=True,
            )

    def get_version_files(self, collection_id: str, version_id: str) -> list[dict]:
        with self._lock:
            self.get_version(collection_id, version_id)
            return [dict(value) for value in self._version_files[version_id]]

    def publish_version(
        self,
        *,
        version: CollectionVersion,
        base_version_id: str | None,
        name: str,
        nodes,
        resources,
        units,
        embedding_profile: str | None,
        manifest_files: list[dict],
    ) -> Collection:
        with self._lock:
            self._validate_projection(version, nodes, resources)
            existing = self._versions.get(version.id)
            if existing is not None:
                if existing != version:
                    raise ConflictError("version ID already exists")
                return self.get(version.collection_id)
            if any(
                item.name == name and item.id != version.collection_id
                for item in self._items.values()
            ):
                raise ConflictError("collection name already exists")
            collection = self._items.get(version.collection_id)
            head = collection.active_version_id if collection else None
            if head != base_version_id:
                raise StaleBaseError(base_version_id, head)
            if version.parent_version_id != head:
                raise ConflictError("version parent does not match current head")
            if version.source_version_id is not None:
                self.get_version(version.collection_id, version.source_version_id)
            collection = collection or Collection(version.collection_id, name)
            self._items[collection.id] = collection
            self.replace_current(
                collection,
                name=name,
                nodes=nodes,
                resources=resources,
                units=units,
                embedding_profile=embedding_profile,
                package_hash=version.package_hash,
            )
            collection.active_version_id = version.id
            self._versions[version.id] = version
            self._version_files[version.id] = [
                _manifest_file(value) for value in manifest_files
            ]
            return collection

    def get_cached_embeddings(self, profile_id, text_sha256s) -> dict[str, list[float]]:
        with self._lock:
            return {
                digest: list(self._embedding_cache[(profile_id, digest)])
                for digest in text_sha256s
                if (profile_id, digest) in self._embedding_cache
            }

    def put_cached_embeddings(
        self, profile_id: str, values: dict[str, list[float]]
    ) -> None:
        with self._lock:
            self._embedding_cache.update(
                {
                    (profile_id, digest): list(embedding)
                    for digest, embedding in values.items()
                }
            )

    def prune_versions(
        self,
        collection_id: str,
        *,
        keep_last: int,
        keep_newer_than: datetime,
    ) -> list[CollectionVersion]:
        if keep_last < 0:
            raise ValueError("keep_last must be non-negative")
        with self._lock:
            collection = self.get(collection_id)
            versions = self.list_versions(collection_id, limit=len(self._versions))
            retained = {value.id for value in versions[:keep_last]}
            retained.update(
                value.id for value in versions if value.created_at >= keep_newer_than
            )
            if collection.active_version_id:
                retained.add(collection.active_version_id)
            removed = [value for value in versions if value.id not in retained]
            removed_ids = {value.id for value in removed}
            for version_id in removed_ids:
                self._versions.pop(version_id, None)
                self._version_files.pop(version_id, None)
            self._clear_removed_references(removed_ids)
            return removed

    @staticmethod
    def _validate_projection(version, nodes, resources) -> None:
        if any(node.collection_id != version.collection_id for node in nodes.values()):
            raise ConflictError("version Collection does not match projection")
        if any(
            resource.collection_id != version.collection_id
            for resource in resources.values()
        ):
            raise ConflictError("version Collection does not match resources")

    def _clear_removed_references(self, removed_ids: set[str]) -> None:
        for version_id, version in list(self._versions.items()):
            parent = (
                None
                if version.parent_version_id in removed_ids
                else version.parent_version_id
            )
            source = (
                None
                if version.source_version_id in removed_ids
                else version.source_version_id
            )
            if (
                parent != version.parent_version_id
                or source != version.source_version_id
            ):
                self._versions[version_id] = replace(
                    version, parent_version_id=parent, source_version_id=source
                )


def _manifest_file(value: dict) -> dict:
    result = {
        key: value[key]
        for key in ("namespace", "logical_path", "sha256", "byte_size", "media_type")
    }
    result["object_key"] = value.get("object_key") or object_key(value["sha256"])
    return result
