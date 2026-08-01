from __future__ import annotations

import csv
import re
from pathlib import Path, PurePosixPath

from reindex_server.domain import safe_relative_path
from reindex_server.node_parser import PackageError


def resolve_uri(card_path: str, uri: str) -> tuple[str, str]:
    if uri.startswith("raw://"):
        return "raw", safe_relative_path(uri.removeprefix("raw://")).as_posix()
    if not uri.startswith("./"):
        raise PackageError(f"unsupported resource URI: {uri}")
    relative = PurePosixPath(card_path).parent / uri.removeprefix("./")
    return "package", safe_relative_path(relative.as_posix()).as_posix()


def validate_tree(cards: dict[str, dict], collection_id: str) -> None:
    if "index.node.md" not in cards:
        raise PackageError("Collection must contain index.node.md")
    root = cards["index.node.md"]
    if str(root["id"]) != collection_id or root["kind"] != "group":
        raise PackageError("Collection root ID must match collection_id and be group")
    if "order" in root:
        raise PackageError("Collection root cannot have order")
    ids: set[str] = set()
    orders: dict[str, list[int]] = {}
    for path, card in cards.items():
        node_id = str(card["id"])
        if node_id in ids:
            raise PackageError(f"duplicate Node id: {node_id}")
        ids.add(node_id)
        parent = parent_card_path(path)
        if parent is None:
            continue
        if parent not in cards:
            raise PackageError(f"missing parent Node card: {path}")
        order = card.get("order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 1:
            raise PackageError(f"invalid Node order: {path}")
        orders.setdefault(parent, []).append(order)
        if PurePosixPath(path).name != "index.node.md" and not PurePosixPath(
            path
        ).name.startswith(f"{order:05d}--"):
            raise PackageError(f"Node filename does not match order: {path}")
    for parent, values in orders.items():
        if sorted(values) != list(range(1, len(values) + 1)):
            raise PackageError(f"child orders must be consecutive: {parent}")


def parent_card_path(path: str) -> str | None:
    value = PurePosixPath(path)
    if path == "index.node.md":
        return None
    if value.name == "index.node.md":
        parent = value.parent.parent / "index.node.md"
    else:
        parent = value.parent / "index.node.md"
    return parent.as_posix()


def validate_asset_name(uri: str, ordinal: int, card_path: str) -> None:
    name = PurePosixPath(uri).name
    if not re.search(rf"\.assets{ordinal:03d}\.[^.]+$", name):
        raise PackageError(f"asset filename does not match ordinal: {card_path}")


def validate_table(metadata: dict, content_file: Path, card_path: str) -> None:
    table = metadata.get("table")
    if metadata["kind"] != "table":
        if table is not None:
            raise PackageError(
                f"only table Nodes may declare table metadata: {card_path}"
            )
        return
    if not isinstance(table, dict):
        raise PackageError(f"table metadata is required: {card_path}")
    with content_file.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))
    if (
        not rows
        or not rows[0]
        or any(not name for name in rows[0])
        or len(set(rows[0])) != len(rows[0])
    ):
        raise PackageError(f"CSV header must be non-empty and unique: {card_path}")
    headers, data = rows[0], rows[1:]
    if any(len(row) != len(headers) for row in data):
        raise PackageError(f"CSV rows do not match header: {card_path}")
    if table.get("row_count") != len(data):
        raise PackageError(f"table row_count mismatch: {card_path}")
    columns = table.get("columns")
    if (
        not isinstance(columns, list)
        or [item.get("name") for item in columns if isinstance(item, dict)] != headers
    ):
        raise PackageError(f"table columns do not match CSV: {card_path}")
    primary = table.get("primary_key", [])
    if not isinstance(primary, list) or any(name not in headers for name in primary):
        raise PackageError(f"invalid table primary_key: {card_path}")
