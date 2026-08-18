from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4, uuid5

from reindex_server.domain import Resource, safe_relative_path
from reindex_server.node_parser import PackageError
from reindex_server.package_import import PackageSnapshot, load_package
from reindex_server.push_import import _raw_references
from reindex_server.storage import object_key


@dataclass
class UploadSession:
    id: str
    collection_id: str
    name: str
    base_version_id: str | None
    manifest: dict
    manifest_sha256: str
    manifest_object_key: str
    message: str
    operation: str
    source_version_id: str | None
    missing_sha256: set[str]
    expires_at: datetime
    uploaded_sha256: set[str] = field(default_factory=set)
    blob_chunks: dict[str, dict[int, tuple[str, int]]] = field(default_factory=dict)
    blob_chunk_counts: dict[str, int] = field(default_factory=dict)
    embeddings: object | None = None
    uploaded_embedding_hashes: set[str] = field(default_factory=set)
    result: dict | None = None

    @classmethod
    def create(
        cls,
        *,
        collection_id: str,
        name: str,
        base_version_id: str | None,
        manifest: dict,
        manifest_sha256: str,
        manifest_object_key: str,
        message: str,
        operation: str,
        source_version_id: str | None,
        missing_sha256: set[str],
        ttl_seconds: int,
    ) -> UploadSession:
        return cls(
            str(uuid4()),
            collection_id,
            name,
            base_version_id,
            manifest,
            manifest_sha256,
            manifest_object_key,
            message,
            operation,
            source_version_id,
            missing_sha256,
            datetime.now(UTC) + timedelta(seconds=ttl_seconds),
        )


def canonical_manifest(manifest: dict) -> tuple[bytes, str]:
    content = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return content, hashlib.sha256(content).hexdigest()


def manifest_file_map(manifest: dict) -> dict[tuple[str, str], dict]:
    return {
        (str(item["namespace"]), str(item["logical_path"])): item
        for item in manifest["files"]
    }


def manifest_hashes(manifest: dict) -> set[str]:
    return {str(item["sha256"]) for item in manifest["files"]}


def load_snapshot_from_manifest(
    manifest: dict, collection_id: str, store
) -> PackageSnapshot:
    files = manifest_file_map(manifest)
    with tempfile.TemporaryDirectory(prefix="reindex-manifest-") as directory:
        package_parent = Path(directory) / "package"
        root = package_parent / str(manifest["package_root"])
        root.mkdir(parents=True)
        for (namespace, logical_path), item in files.items():
            if namespace != "package":
                continue
            target = root / safe_relative_path(logical_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            _copy_object(store, str(item["sha256"]), target)
        references = _raw_references(root)
        raw_files = {
            path: item
            for (namespace, path), item in files.items()
            if namespace == "raw"
        }
        if set(raw_files) != set(references):
            missing = sorted(set(references) - set(raw_files))
            extra = sorted(set(raw_files) - set(references))
            detail = []
            if missing:
                detail.append(f"missing sources: {', '.join(missing)}")
            if extra:
                detail.append(f"unreferenced sources: {', '.join(extra)}")
            raise PackageError("; ".join(detail))
        resources = _raw_resources(collection_id, raw_files, references)
        return load_package(package_parent, collection_id, store, resources)


def _raw_resources(collection_id: str, files: dict, references: dict):
    result = {}
    for logical_path, item in files.items():
        expected = references[logical_path]
        if str(item["sha256"]) != expected["sha256"]:
            raise PackageError(f"raw resource hash mismatch: {logical_path}")
        resource = Resource(
            str(uuid5(UUID(collection_id), f"raw:{logical_path}")),
            collection_id,
            "raw",
            logical_path,
            Path(logical_path).name,
            str(item["sha256"]),
            int(item["byte_size"]),
            str(expected["media_type"]),
            object_key(str(item["sha256"])),
        )
        result[("raw", logical_path)] = resource
    return result


def _copy_object(store, sha256: str, target: Path) -> None:
    if not store.exists(sha256):
        raise PackageError(f"missing uploaded blob: {sha256}")
    with store.open(object_key(sha256)) as source, target.open("wb") as output:
        shutil.copyfileobj(source, output, 1024 * 1024)
