from __future__ import annotations

import csv
import hashlib
import re
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
            if (
                path.is_absolute()
                or ".." in path.parts
                or item.is_dir()
                or (item.external_attr >> 16) & 0o170000 == 0o120000
            ):
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
    if (
        not isinstance(metadata, dict)
        or metadata.get("spec") != "reindex/node@0.1"
        or not required <= metadata.keys()
    ):
        raise PackageError(f"invalid Node metadata: {relative}")
    return node_from_frontmatter(relative, metadata, parts[2].lstrip("\n"), parent_id)


def _read_node(file: Path, relative: str, parent_id: str | None) -> Node:
    return parse_node(file.read_text(encoding="utf-8"), relative, parent_id)


def load_package(
    root: Path,
    collection_id: str,
    store: FileStore,
    revision_id: str,
    raw: dict[str, str],
) -> tuple[dict[str, Node], list[SearchUnit]]:
    files = sorted(
        root.rglob("*.node.md"),
        key=lambda item: (
            len(item.relative_to(root).parts),
            item.name != "index.node.md",
            item.as_posix(),
        ),
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
        parent_file = (
            file.parent / "index.node.md" if file.name != "index.node.md" else None
        )
        if file.name == "index.node.md" and file.parent != root:
            parent_file = file.parent.parent / "index.node.md"
        parent = (
            by_path.get(parent_file.relative_to(root).as_posix())
            if parent_file and parent_file.exists()
            else None
        )
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
            expected = (
                (
                    yaml.safe_load(file.read_text(encoding="utf-8").split("---", 2)[1])
                    or {}
                )
                .get("resource", {})
                .get("sha256")
            )
            actual = hashlib.sha256(resource.read_bytes()).hexdigest()
            if actual != expected:
                raise PackageError(f"resource hash mismatch: {node.resource_uri}")
            node.resource_key = store.copy_resource(
                collection_id,
                revision_id,
                resource,
                f"resources/{relative}/{resource.name}",
            )
        ids.add(node.id)
        by_path[relative] = node
    root_node = by_path["index.node.md"]
    if root_node.id != collection_id:
        raise PackageError("archive root Node must match collection_id")
    return {node.id: node for node in by_path.values()}, _search_units(
        by_path.values(), store
    )


def _search_units(nodes: Iterable[Node], store: FileStore) -> list[SearchUnit]:
    units: list[SearchUnit] = []
    for node in nodes:
        for ordinal, (original_text, start_line, end_line) in enumerate(
            _markdown_chunks(node.body), 1
        ):
            units.append(
                SearchUnit(
                    id=f"{node.id}:text:{ordinal}",
                    node_id=node.id,
                    contextual_text="\n".join(
                        (node.title, node.description, original_text)
                    ),
                    original_text=original_text,
                    start_line=start_line,
                    end_line=end_line,
                    ordinal=ordinal,
                    locator=node.locator,
                )
            )
        if node.kind == "table" and node.resource_key:
            resource = store.resource_file(node.resource_key)
            with resource.open(encoding="utf-8", newline="") as stream:
                for number, row in enumerate(csv.DictReader(stream), 1):
                    text = " | ".join(f"{name}: {value}" for name, value in row.items())
                    units.append(
                        SearchUnit(
                            id=f"{node.id}:row:{number}",
                            node_id=node.id,
                            contextual_text="\n".join(
                                (node.title, node.description, text)
                            ),
                            original_text=text,
                            start_line=None,
                            end_line=None,
                            ordinal=number,
                            row=number,
                            locator=node.locator,
                        )
                    )
    return units


def _markdown_chunks(
    body: str, target_tokens: int = 600, overlap_tokens: int = 80
) -> list[tuple[str, int, int]]:
    """Split Markdown at paragraph/list boundaries while preserving source line ranges."""
    lines = body.splitlines()
    if not lines:
        return [("", 1, 1)]
    blocks: list[tuple[list[str], int, int]] = []
    current: list[str] = []
    start = 1
    for number, line in enumerate(lines, 1):
        if line.strip() == "" and current:
            blocks.append((current, start, number - 1))
            current, start = [], number + 1
        else:
            if not current:
                start = number
            current.append(line)
    if current:
        blocks.append((current, start, len(lines)))

    chunks: list[tuple[str, int, int]] = []
    pending: list[tuple[list[str], int, int]] = []
    token_count = 0
    for block in blocks:
        block_tokens = len(re.findall(r"\S+", "\n".join(block[0])))
        if pending and token_count + block_tokens > target_tokens:
            text = "\n\n".join("\n".join(value[0]) for value in pending)
            chunks.append((text, pending[0][1], pending[-1][2]))
            overlap: list[tuple[list[str], int, int]] = []
            seen = 0
            for value in reversed(pending):
                overlap.insert(0, value)
                seen += len(re.findall(r"\S+", "\n".join(value[0])))
                if seen >= overlap_tokens:
                    break
            pending, token_count = overlap, seen
        pending.append(block)
        token_count += block_tokens
    if pending:
        text = "\n\n".join("\n".join(value[0]) for value in pending)
        chunks.append((text, pending[0][1], pending[-1][2]))
    return chunks
