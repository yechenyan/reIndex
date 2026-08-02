from __future__ import annotations

import mimetypes
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid5

from reindex_server.domain import Resource, safe_relative_path
from reindex_server.node_parser import PackageError, parse_node_card
from reindex_server.package_import import (
    PackageSnapshot,
    _collection_root,
    load_package,
    unpack_archive,
)

_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$")


@dataclass(frozen=True)
class PreparedPush:
    name: str
    collection_id: str
    snapshot: PackageSnapshot
    source_count: int


def prepare_push(
    name: str, package_archive: Path, sources_archive: Path, store
) -> PreparedPush:
    if not _NAME.fullmatch(name):
        raise PackageError(
            "collection name must contain lowercase letters, digits, or hyphens"
        )
    with tempfile.TemporaryDirectory(prefix="reindex-push-") as directory:
        work = Path(directory)
        package_dir = work / "package"
        source_dir = work / "sources"
        package_dir.mkdir()
        source_dir.mkdir()
        unpack_archive(package_archive, package_dir)
        unpack_archive(sources_archive, source_dir)
        root = _collection_root(package_dir)
        root_card = parse_node_card(
            (root / "index.node.md").read_bytes(), "index.node.md"
        )
        collection_id = str(root_card.metadata["id"])
        references = _raw_references(root)
        files = {
            file.relative_to(source_dir).as_posix(): file
            for file in source_dir.rglob("*")
            if file.is_file()
        }
        if set(files) != set(references):
            missing = sorted(set(references) - set(files))
            extra = sorted(set(files) - set(references))
            details = []
            if missing:
                details.append(f"missing sources: {', '.join(missing)}")
            if extra:
                details.append(f"unreferenced sources: {', '.join(extra)}")
            raise PackageError("; ".join(details))
        resources = _raw_resources(collection_id, files, references, store)
        snapshot = load_package(package_dir, collection_id, store, resources)
        return PreparedPush(name, collection_id, snapshot, len(files))


def _raw_references(root: Path) -> dict[str, dict[str, str]]:
    references: dict[str, dict[str, str]] = {}
    for card_file in root.rglob("*.node.md"):
        relative = card_file.relative_to(root).as_posix()
        card = parse_node_card(card_file.read_bytes(), relative).metadata
        values = [card.get("source"), card.get("content"), *card.get("assets", [])]
        for value in values:
            if not isinstance(value, dict) or not str(value.get("uri", "")).startswith(
                "raw://"
            ):
                continue
            logical = safe_relative_path(value["uri"].removeprefix("raw://")).as_posix()
            record = {
                "sha256": str(value["sha256"]),
                "media_type": str(
                    value.get("media_type")
                    or mimetypes.guess_type(logical)[0]
                    or "application/octet-stream"
                ),
            }
            if (
                logical in references
                and references[logical]["sha256"] != record["sha256"]
            ):
                raise PackageError(f"conflicting raw hashes: {logical}")
            references[logical] = record
    return references


def _raw_resources(collection_id, files, references, store):
    result = {}
    for logical_path, file in files.items():
        stored = store.put_file(file)
        expected = references[logical_path]
        if stored.sha256 != expected["sha256"]:
            raise PackageError(f"raw resource hash mismatch: {logical_path}")
        item = Resource(
            str(uuid5(UUID(collection_id), f"raw:{logical_path}")),
            collection_id,
            "raw",
            logical_path,
            Path(logical_path).name,
            stored.sha256,
            stored.byte_size,
            expected["media_type"],
            stored.object_key,
        )
        result[("raw", logical_path)] = item
    return result
