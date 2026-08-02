from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import RLock
from uuid import uuid4

from reindex_server.domain import CollectionVersion, SearchUnit
from reindex_server.errors import ConflictError, StaleBaseError
from reindex_server.push_protocol import (
    UploadSession,
    canonical_manifest,
    load_snapshot_from_manifest,
    manifest_hashes,
)
from reindex_server.version_serialization import unique_blobs, version_json


class PublicationManager:
    def __init__(self, catalog, store, embeddings) -> None:
        self.catalog = catalog
        self.store = store
        self.embeddings = embeddings
        self._sessions: dict[str, UploadSession] = {}
        self._lock = RLock()
        self.session_ttl_seconds = 24 * 60 * 60
        self.gc_grace_seconds = 24 * 60 * 60

    def start(self, request) -> dict:
        self._expire_sessions()
        collection_id = str(request.collection_id)
        base = str(request.base_version_id) if request.base_version_id else None
        manifest = request.manifest.model_dump(mode="json")
        content, manifest_sha = canonical_manifest(manifest)
        head = self.catalog.current_version(collection_id)
        self._check_name(collection_id, request.name)
        self._check_base(base, head.id if head else None)
        if request.source_version_id:
            self.catalog.get_version(collection_id, str(request.source_version_id))
        try:
            collection = self.catalog.get(collection_id)
        except KeyError:
            collection = None
        if (
            head
            and head.manifest_sha256 == manifest_sha
            and collection
            and collection.name == request.name
            and request.operation == "publish"
        ):
            return self._start_response(head, [], None, True, collection.package_hash)
        unique = unique_blobs(manifest)
        missing = [
            item
            for item in unique.values()
            if self.store.size(str(item["sha256"])) != int(item["byte_size"])
        ]
        if request.dry_run:
            return self._start_response(head, missing, None, False, None, "planned")
        stored = self.store.put_bytes(content)
        session = UploadSession.create(
            collection_id=collection_id,
            name=request.name,
            base_version_id=base,
            manifest=manifest,
            manifest_sha256=manifest_sha,
            manifest_object_key=stored.object_key,
            message=request.message,
            operation=request.operation,
            source_version_id=(
                str(request.source_version_id) if request.source_version_id else None
            ),
            missing_sha256={str(item["sha256"]) for item in missing},
            ttl_seconds=self.session_ttl_seconds,
        )
        with self._lock:
            self._sessions[session.id] = session
        return self._start_response(head, missing, session, False, None)

    def upload_blob(self, upload_id: str, expected_sha256: str, path: Path) -> dict:
        session = self._session(upload_id)
        declared = unique_blobs(session.manifest).get(expected_sha256)
        if declared is None:
            raise ValueError("blob is not declared by this upload session")
        existed = self.store.size(expected_sha256) == int(declared["byte_size"])
        stored = self.store.put_file(path)
        if stored.sha256 != expected_sha256:
            raise ValueError("uploaded blob SHA-256 mismatch")
        if stored.byte_size != int(declared["byte_size"]):
            raise ValueError("uploaded blob size mismatch")
        session.uploaded_sha256.add(expected_sha256)
        session.missing_sha256.discard(expected_sha256)
        return {
            "status": "reused" if existed else "stored",
            "sha256": stored.sha256,
            "byte_size": stored.byte_size,
        }

    def commit(self, upload_id: str) -> dict:
        session = self._session(upload_id)
        if session.result is not None:
            return session.result
        head = self.catalog.current_version(session.collection_id)
        self._check_base(session.base_version_id, head.id if head else None)
        unique = unique_blobs(session.manifest)
        unavailable = [
            digest
            for digest, item in unique.items()
            if self.store.size(digest) != int(item["byte_size"])
        ]
        if unavailable:
            raise ValueError(f"upload is missing {len(unavailable)} blob(s)")
        snapshot = load_snapshot_from_manifest(
            session.manifest, session.collection_id, self.store
        )
        profile, embedded, reused = self._embed(snapshot.units)
        stats = {
            "nodes": len(snapshot.nodes),
            "sources": sum(
                item["namespace"] == "raw" for item in session.manifest["files"]
            ),
            "resources": len(snapshot.resources),
            "search_units": len(snapshot.units),
            "embedded_units": embedded,
            "reused_embeddings": reused,
        }
        version = CollectionVersion(
            str(uuid4()),
            session.collection_id,
            session.base_version_id,
            snapshot.package_hash,
            session.manifest_sha256,
            session.manifest_object_key,
            session.message,
            session.operation,
            session.source_version_id,
            datetime.now(UTC),
            stats,
        )
        collection = self.catalog.publish_version(
            version=version,
            base_version_id=session.base_version_id,
            name=session.name,
            nodes=snapshot.nodes,
            resources=snapshot.resources,
            units=snapshot.units,
            embedding_profile=profile,
            manifest_files=session.manifest["files"],
        )
        session.result = {
            "status": "ready",
            "name": collection.name,
            "collection_id": collection.id,
            "version_id": version.id,
            "parent_version_id": version.parent_version_id,
            "package_hash": version.package_hash,
            "operation": version.operation,
            "source_version_id": version.source_version_id,
            **stats,
            "embedding_profile": profile,
            "uploaded_blobs": len(session.uploaded_sha256),
            "reused_blobs": len(unique) - len(session.uploaded_sha256),
            "no_op": False,
        }
        self._maintain(session.collection_id)
        return session.result

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
        next_cursor = str(offset + limit) if len(values) > offset + limit else None
        return {
            "name": collection.name,
            "collection_id": collection.id,
            "versions": [
                version_json(item, collection.active_version_id) for item in page
            ],
            "next_cursor": next_cursor,
        }

    def _embed(self, units: list[SearchUnit]) -> tuple[str | None, int, int]:
        if self.embeddings.name == "disabled":
            return None, 0, 0
        hashes = [
            hashlib.sha256(item.contextual_text.encode()).hexdigest() for item in units
        ]
        cached = self.catalog.get_cached_embeddings(self.embeddings.name, set(hashes))
        missing_text = {
            digest: unit.contextual_text
            for digest, unit in zip(hashes, units, strict=True)
            if digest not in cached
        }
        if missing_text:
            vectors = self.embeddings.embed_documents(missing_text.values())
            created = dict(zip(missing_text, vectors, strict=True))
            self.catalog.put_cached_embeddings(self.embeddings.name, created)
            cached.update(created)
        for digest, unit in zip(hashes, units, strict=True):
            unit.embedding = cached[digest]
        return self.embeddings.name, len(missing_text), len(units) - len(missing_text)

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

    def _session(self, upload_id: str) -> UploadSession:
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

    def _check_name(self, collection_id: str, name: str) -> None:
        try:
            existing = self.catalog.get_by_name(name)
        except KeyError:
            return
        if existing.id != collection_id:
            raise ConflictError("collection name already exists")

    @staticmethod
    def _check_base(base: str | None, head: str | None) -> None:
        if base != head:
            raise StaleBaseError(base, head)

    @staticmethod
    def _start_response(
        head, missing, session, no_op, package_hash, status="upload"
    ) -> dict:
        return {
            "status": "ready" if no_op else status,
            "upload_id": session.id if session else None,
            "expires_at": session.expires_at.isoformat() if session else None,
            "head_version_id": head.id if head else None,
            "package_hash": package_hash,
            "missing_blobs": missing,
            "no_op": no_op,
        }
