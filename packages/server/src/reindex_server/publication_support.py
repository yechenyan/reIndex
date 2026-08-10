from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from reindex_server.push_protocol import manifest_hashes
from reindex_server.version_serialization import version_json


class PublicationSupportMixin:
    def fetch(self, collection_name: str, version_id: str | None = None) -> dict:
        collection = self.catalog.get_by_name(collection_name)
        version = (
            self.catalog.get_version(collection.id, version_id)
            if version_id
            else self.catalog.current_version(collection.id)
        )
        if version is None:
            raise KeyError("Collection has no published version")
        with self.store.open(version.manifest_object_key) as stream:
            manifest = json.load(stream)
        return {
            "name": collection.name,
            "collection_id": collection.id,
            "version": version_json(version, collection.active_version_id),
            "manifest": manifest,
        }

    def history(self, collection_name: str, limit: int, cursor: str | None) -> dict:
        collection = self.catalog.get_by_name(collection_name)
        offset = int(cursor or 0)
        if offset < 0:
            raise ValueError("history cursor must be non-negative")
        values = self.catalog.list_versions(
            collection.id, limit=offset + limit + 1, before=None
        )
        page = values[offset : offset + limit]
        return {
            "name": collection.name,
            "collection_id": collection.id,
            "versions": [
                version_json(item, collection.active_version_id) for item in page
            ],
            "next_cursor": str(offset + limit)
            if len(values) > offset + limit
            else None,
        }

    def _embed(self, units, supplied=None) -> tuple[str | None, int, int]:
        profile = supplied.profile if supplied else self.embeddings.name
        if profile == "disabled":
            return None, 0, 0
        hashes = [
            hashlib.sha256(item.contextual_text.encode()).hexdigest() for item in units
        ]
        provided = supplied.vectors if supplied else {}
        if set(provided) - set(hashes):
            raise ValueError("embedding vectors do not belong to this Collection")
        cached = self.catalog.get_cached_embeddings(profile, set(hashes))
        imported = {key: value for key, value in provided.items() if key not in cached}
        if imported:
            self.catalog.put_cached_embeddings(profile, imported)
            cached.update(imported)
        missing = {
            key: unit.contextual_text
            for key, unit in zip(hashes, units, strict=True)
            if key not in cached
        }
        if missing:
            if self.embeddings.name == "disabled" or self.embeddings.name != profile:
                raise ValueError("local embedding upload does not cover every search unit")
            created = dict(
                zip(
                    missing,
                    self.embeddings.embed_documents(missing.values()),
                    strict=True,
                )
            )
            self.catalog.put_cached_embeddings(profile, created)
            cached.update(created)
        for key, unit in zip(hashes, units, strict=True):
            unit.embedding = cached[key]
        return (
            profile,
            len(imported) + len(missing),
            len(units) - len(imported) - len(missing),
        )

    def _maintain(self, collection_id: str) -> None:
        self.catalog.prune_versions(
            collection_id,
            keep_last=10,
            keep_newer_than=datetime.now(UTC) - timedelta(days=30),
        )
        retained = {item.manifest_sha256 for item in self.catalog.list_all_versions()}
        for version in self.catalog.list_all_versions():
            with self.store.open(version.manifest_object_key) as stream:
                retained.update(manifest_hashes(json.load(stream)))
        with self._lock:
            for session in self._sessions.values():
                retained.add(session.manifest_sha256)
                retained.update(manifest_hashes(session.manifest))
        self.store.sweep(retained, self.gc_grace_seconds)

    def _session(self, upload_id: str):
        self._expire_sessions()
        with self._lock:
            try:
                return self._sessions[upload_id]
            except KeyError as error:
                raise KeyError("upload session not found or expired") from error

    def _expire_sessions(self) -> None:
        now = datetime.now(UTC)
        with self._lock:
            self._sessions = {
                key: value
                for key, value in self._sessions.items()
                if value.expires_at > now
            }
