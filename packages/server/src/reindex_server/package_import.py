from __future__ import annotations

import hashlib
import json
import mimetypes
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid5

from reindex_server.domain import Node, NodeResource, Resource, SearchUnit
from reindex_server.node_parser import PackageError, parse_node_card
from reindex_server.package_validation import (
    parent_card_path,
    resolve_uri,
    validate_asset_name,
    validate_table,
    validate_tree,
)
from reindex_server.search_projection import build_search_units, markdown_chunks
from reindex_server.storage import ObjectStore


@dataclass(frozen=True)
class PackageSnapshot:
    name: str
    package_hash: str
    nodes: dict[str, Node]
    resources: dict[tuple[str, str], Resource]
    units: list[SearchUnit]


def unpack_archive(archive: Path, target: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        names: set[str] = set()
        for item in bundle.infolist():
            path = PurePosixPath(item.filename)
            if item.filename in names:
                raise PackageError(f"duplicate archive entry: {item.filename}")
            names.add(item.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or (item.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise PackageError(f"unsafe archive entry: {item.filename}")
            if item.is_dir():
                continue
            destination = target.joinpath(*path.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(item) as source, destination.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)


def load_package(
    unpacked: Path,
    collection_id: str,
    store: ObjectStore,
    existing: dict[tuple[str, str], Resource],
) -> PackageSnapshot:
    root = _collection_root(unpacked)
    card_files = sorted(
        root.rglob("*.node.md"),
        key=lambda file: (
            len(file.relative_to(root).parts),
            file.name != "index.node.md",
            file.as_posix(),
        ),
    )
    parsed = {
        file.relative_to(root).as_posix(): parse_node_card(
            file.read_bytes(), file.relative_to(root).as_posix()
        )
        for file in card_files
    }
    validate_tree({path: card.metadata for path, card in parsed.items()}, collection_id)
    resources = {key: value for key, value in existing.items() if key[0] == "raw"}
    nodes: dict[str, Node] = {}
    used_paths: set[str] = set()
    for path, card in parsed.items():
        node = _build_node(
            root, path, card, collection_id, nodes, resources, used_paths, store
        )
        nodes[node.id] = node
    all_paths = {
        file.relative_to(root).as_posix() for file in root.rglob("*") if file.is_file()
    }
    if extras := all_paths - used_paths:
        raise PackageError(f"unreferenced package files: {', '.join(sorted(extras))}")
    manifest = [
        {
            "id": node.id,
            "path": node.path,
            "parent_id": node.parent_id,
            "order": node.order,
            "node_hash": node.node_hash,
            "resources": [
                {
                    "role": link.role,
                    "ordinal": link.ordinal,
                    "namespace": link.resource.namespace,
                    "logical_path": link.resource.logical_path,
                    "sha256": link.resource.sha256,
                }
                for link in sorted(
                    node.resources, key=lambda value: (value.role, value.ordinal)
                )
            ],
        }
        for node in sorted(nodes.values(), key=lambda value: value.path)
    ]
    package_hash = hashlib.sha256(
        json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    return PackageSnapshot(
        root.name,
        package_hash,
        nodes,
        resources,
        build_search_units(nodes.values(), store),
    )


def _collection_root(unpacked: Path) -> Path:
    entries = [item for item in unpacked.iterdir() if item.name != "__MACOSX"]
    if len(entries) != 1 or not entries[0].is_dir():
        raise PackageError("archive must contain exactly one Collection directory")
    root = entries[0]
    if not (root / "index.node.md").is_file():
        raise PackageError("Collection directory must contain index.node.md")
    return root


def _build_node(
    root, path, card, collection_id, nodes, resources, used_paths, store
) -> Node:
    metadata = card.metadata
    parent_path = parent_card_path(path)
    parent = next((node for node in nodes.values() if node.path == parent_path), None)
    if parent_path and parent is None:
        raise PackageError(f"parent must appear before child: {path}")
    order = metadata.get("order")
    tree_path = (
        (*parent.tree_path, str(metadata["id"])) if parent else (str(metadata["id"]),)
    )
    order_path = (*parent.order_path, order) if parent else ()
    links = [
        NodeResource(
            "card",
            0,
            _package_resource(
                root, path, "text/markdown", collection_id, resources, used_paths, store
            ),
        )
    ]
    if source := metadata.get("source"):
        links.append(
            _link(
                root,
                path,
                source,
                "source",
                0,
                collection_id,
                resources,
                used_paths,
                store,
                locator=source.get("locator"),
            )
        )
    if content := metadata.get("content"):
        links.append(
            _link(
                root,
                path,
                content,
                "content",
                0,
                collection_id,
                resources,
                used_paths,
                store,
            )
        )
        if metadata["kind"] == "table":
            namespace, logical_path = resolve_uri(path, content["uri"])
            if namespace != "package":
                raise PackageError(f"table content must be a package CSV: {path}")
            validate_table(metadata, root / logical_path, path)
    else:
        validate_table(metadata, root / "unused", path)
    for ordinal, asset in enumerate(metadata.get("assets", []), 1):
        validate_asset_name(asset["uri"], ordinal, path)
        links.append(
            _link(
                root,
                path,
                asset,
                "asset",
                ordinal,
                collection_id,
                resources,
                used_paths,
                store,
                asset_role=asset["role"],
                description=asset["description"],
            )
        )
    attributes = {
        key: value
        for key, value in metadata.items()
        if key
        not in {
            "spec",
            "id",
            "kind",
            "order",
            "title",
            "description",
            "source",
            "content",
            "assets",
        }
    }
    digest_input = (
        json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        + card.markdown
        + "\n"
        + "\n".join(link.resource.sha256 for link in links)
    )
    return Node(
        str(metadata["id"]),
        collection_id,
        path,
        parent.id if parent else None,
        order,
        tree_path,
        order_path,
        metadata["kind"],
        metadata["title"],
        metadata["description"],
        card.markdown,
        attributes,
        hashlib.sha256(digest_input.encode()).hexdigest(),
        links,
    )


def _link(
    root,
    card_path,
    value,
    role,
    ordinal,
    collection_id,
    resources,
    used_paths,
    store,
    **metadata,
):
    namespace, logical_path = resolve_uri(card_path, value["uri"])
    if namespace == "raw":
        try:
            resource = resources[(namespace, logical_path)]
        except KeyError as error:
            raise PackageError(f"missing raw resource: {logical_path}") from error
        if resource.sha256 != value["sha256"]:
            raise PackageError(f"raw resource hash mismatch: {logical_path}")
    else:
        resource = _package_resource(
            root,
            logical_path,
            value["media_type"],
            collection_id,
            resources,
            used_paths,
            store,
            value["sha256"],
        )
    return NodeResource(role, ordinal, resource, **metadata)


def _package_resource(
    root,
    logical_path,
    media_type,
    collection_id,
    resources,
    used_paths,
    store,
    expected=None,
):
    file = root / logical_path
    if not file.is_file():
        raise PackageError(f"missing package resource: {logical_path}")
    stored = store.put_file(file)
    if expected and stored.sha256 != expected:
        raise PackageError(f"package resource hash mismatch: {logical_path}")
    used_paths.add(logical_path)
    resource = Resource(
        str(uuid5(UUID(collection_id), f"package:{logical_path}")),
        collection_id,
        "package",
        logical_path,
        file.name,
        stored.sha256,
        stored.byte_size,
        media_type or mimetypes.guess_type(file.name)[0] or "application/octet-stream",
        stored.object_key,
    )
    resources[("package", logical_path)] = resource
    return resource


_markdown_chunks = markdown_chunks
