from __future__ import annotations

import mimetypes
from pathlib import Path

from reindex_cli.archives import raw_references
from reindex_cli.errors import ReIndexError
from reindex_cli.util import sha256_file


def build_transport_manifest(context) -> tuple[dict, dict[str, Path]]:
    files: list[dict] = []
    blobs: dict[str, Path] = {}
    for path in sorted(context.output_dir.rglob("*")):
        if path.is_file():
            _append(
                files,
                blobs,
                "package",
                path.relative_to(context.output_dir).as_posix(),
                path,
            )
    for logical_path, expected in sorted(raw_references(context.output_dir).items()):
        path = context.root / logical_path
        if not path.is_file() or sha256_file(path) != expected:
            raise ReIndexError(f"Missing or changed source: {logical_path}")
        _append(files, blobs, "raw", logical_path, path)
    return (
        {
            "spec": "reindex/transport@1.0",
            "package_root": context.output_dir.name,
            "files": files,
        },
        blobs,
    )


def manifest_changes(base: dict | None, other: dict) -> dict:
    before = _entries(base)
    after = _entries(other)
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(
        key for key in set(before) & set(after) if before[key] != after[key]
    )
    return {
        "added": [_label(key) for key in added],
        "changed": [_label(key) for key in changed],
        "removed": [_label(key) for key in removed],
    }


def changed_keys(base: dict | None, other: dict) -> set[tuple[str, str]]:
    changes = manifest_changes(base, other)
    return {_unlabel(value) for group in changes.values() for value in group}


def _append(files, blobs, namespace: str, logical_path: str, path: Path) -> None:
    digest = sha256_file(path)
    blobs.setdefault(digest, path)
    files.append(
        {
            "namespace": namespace,
            "logical_path": logical_path,
            "sha256": digest,
            "byte_size": path.stat().st_size,
            "media_type": mimetypes.guess_type(path.name)[0]
            or "application/octet-stream",
        }
    )


def _entries(manifest: dict | None) -> dict[tuple[str, str], tuple[str, int]]:
    if not manifest:
        return {}
    return {
        (str(item["namespace"]), str(item["logical_path"])): (
            str(item["sha256"]),
            int(item["byte_size"]),
        )
        for item in manifest.get("files", [])
    }


def _label(key: tuple[str, str]) -> str:
    return f"{key[0]}:{key[1]}"


def _unlabel(value: str) -> tuple[str, str]:
    namespace, logical_path = value.split(":", 1)
    return namespace, logical_path
