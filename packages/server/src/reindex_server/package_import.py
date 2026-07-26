from __future__ import annotations

import csv
import hashlib
import zipfile
from collections.abc import Iterable
from pathlib import Path

import yaml

from reindex_server.domain import Node, SearchUnit, node_from_frontmatter
from reindex_server.storage import FileStore


class PackageError(ValueError):
    pass


def unpack_archive(archive: Path, target: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            path = Path(item.filename)
            if path.is_absolute() or ".." in path.parts or item.is_dir() or (item.external_attr >> 16) & 0o170000 == 0o120000:
                if not item.is_dir():
                    raise PackageError(f"unsafe archive entry: {item.filename}")
                continue
            destination = target / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(item) as source, destination.open("wb") as output:
                output.write(source.read())


def parse_node(content: str, relative: str, parent_id: str | None = None) -> Node:
    parts = content.split("---", 2)
    if len(parts) != 3 or parts[0]:
        raise PackageError(f"invalid frontmatter: {relative}")
    try:
        metadata = yaml.safe_load(parts[1])
    except yaml.YAMLError as error:
        raise PackageError(f"invalid YAML: {relative}") from error
    required = {"spec", "id", "kind", "title", "description"}
    if not isinstance(metadata, dict) or metadata.get("spec") != "reindex/node@0.1" or not required <= metadata.keys():
        raise PackageError(f"invalid Node metadata: {relative}")
    return node_from_frontmatter(relative, metadata, parts[2].lstrip("\n"), parent_id)


def _read_node(file: Path, relative: str, parent_id: str | None) -> Node:
    return parse_node(file.read_text(encoding="utf-8"), relative, parent_id)


def load_package(root: Path, collection_id: str, store: FileStore, revision_id: str, raw: dict[str, str]) -> tuple[dict[str, Node], list[SearchUnit]]:
    files = sorted(
        root.rglob("*.node.md"),
        key=lambda item: (len(item.relative_to(root).parts), item.name != "index.node.md", item.as_posix()),
    )
    if not files:
        raise PackageError("archive has no Node files")
    root_file = root / "index.node.md"
    if not root_file.is_file():
        raise PackageError("archive must contain root index.node.md")
    by_path: dict[str, Node] = {}
    ids: set[str] = set()
    for file in files:
        relative = file.relative_to(root).as_posix()
        parent_file = file.parent / "index.node.md" if file.name != "index.node.md" else None
        if file.name == "index.node.md" and file.parent != root:
            parent_file = file.parent.parent / "index.node.md"
        parent = by_path.get(parent_file.relative_to(root).as_posix()) if parent_file and parent_file.exists() else None
        node = _read_node(file, relative, parent.id if parent else None)
        if node.id in ids:
            raise PackageError(f"duplicate Node id: {node.id}")
        if node.source_uri:
            if not node.source_uri.startswith("raw://"):
                raise PackageError(f"unsupported source URI: {node.source_uri}")
            raw_path = node.source_uri.removeprefix("raw://")
            expected = raw.get(raw_path)
            if expected != node.source_sha256:
                raise PackageError(f"missing or mismatched raw source: {raw_path}")
        if node.resource_uri:
            resource = file.parent / node.resource_uri.removeprefix("./")
            if not resource.is_file():
                raise PackageError(f"missing resource: {node.resource_uri}")
            expected = (yaml.safe_load(file.read_text(encoding="utf-8").split("---", 2)[1]) or {}).get("resource", {}).get("sha256")
            actual = hashlib.sha256(resource.read_bytes()).hexdigest()
            if actual != expected:
                raise PackageError(f"resource hash mismatch: {node.resource_uri}")
            node.resource_key = store.copy_resource(collection_id, revision_id, resource, f"resources/{relative}/{resource.name}")
        ids.add(node.id)
        by_path[relative] = node
    root_node = by_path["index.node.md"]
    if root_node.id != collection_id:
        raise PackageError("archive root Node must match collection_id")
    return {node.id: node for node in by_path.values()}, _search_units(by_path.values(), store)


def _search_units(nodes: Iterable[Node], store: FileStore) -> list[SearchUnit]:
    units: list[SearchUnit] = []
    for node in nodes:
        text = "\n".join((node.title, node.description, node.body))
        units.append(SearchUnit(node.id, text, node.body[:800] or node.description))
        if node.kind == "table" and node.resource_key:
            resource = store.resource_file(node.resource_key)
            with resource.open(encoding="utf-8", newline="") as stream:
                for number, row in enumerate(csv.DictReader(stream), 1):
                    text = " | ".join(f"{name}: {value}" for name, value in row.items())
                    units.append(SearchUnit(node.id, text, text[:800], row=number))
    return units
