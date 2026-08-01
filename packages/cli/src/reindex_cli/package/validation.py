from __future__ import annotations

import csv
import re
from pathlib import Path, PurePosixPath
from uuid import UUID

from reindex_cli.errors import PackageError
from reindex_cli.package.cards import machine_hash, parse_card
from reindex_cli.util import sha256_file


def validate_package(
    package: Path,
    raw_root: Path,
    collection_id: str,
    expected_nodes: dict[str, dict] | None = None,
) -> dict:
    cards = {
        path.relative_to(package).as_posix(): parse_card(path)
        for path in package.rglob("*.node.md")
    }
    if "index.node.md" not in cards:
        raise PackageError("Collection package requires index.node.md")
    metadata = {path: value[0] for path, value in cards.items()}
    _validate_tree(metadata, collection_id)
    used = set(cards)
    for card_path, (card, _body) in cards.items():
        _validate_metadata(card, card_path)
        _validate_resources(package, raw_root, card_path, card, used)
        if card["kind"] == "table":
            _validate_table(package, card_path, card)
        if expected_nodes is not None:
            record = expected_nodes.get(str(card["id"]))
            if not record or machine_hash(card) != record.get("machine_sha256"):
                raise PackageError(f"CLI-owned Node metadata changed: {card_path}")
    files = {
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file()
    }
    if extras := files - used:
        raise PackageError(f"unreferenced package files: {', '.join(sorted(extras))}")
    return {"nodes": len(cards), "files": len(files)}


def _validate_tree(cards: dict[str, dict], collection_id: str) -> None:
    root = cards["index.node.md"]
    if (
        str(root.get("id")) != collection_id
        or root.get("kind") != "group"
        or "order" in root
    ):
        raise PackageError("Collection root ID/kind/order is invalid")
    ids: set[str] = set()
    orders: dict[str, list[int]] = {}
    for path, card in cards.items():
        node_id = str(card.get("id"))
        if node_id in ids:
            raise PackageError(f"duplicate Node ID: {node_id}")
        ids.add(node_id)
        if path == "index.node.md":
            continue
        parent = _parent_card(path)
        if parent not in cards:
            raise PackageError(f"missing parent card: {path}")
        order = card.get("order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 1:
            raise PackageError(f"invalid Node order: {path}")
        orders.setdefault(parent, []).append(order)
        value = PurePosixPath(path)
        if value.name != "index.node.md":
            if value.parent == PurePosixPath("."):
                if re.match(r"^\d{5}--", value.name):
                    raise PackageError(
                        f"Collection root Node filename must not use an order prefix: {path}"
                    )
            elif not value.name.startswith(f"{order:05d}--"):
                raise PackageError(f"filename does not match order: {path}")
    for parent, values in orders.items():
        if sorted(values) != list(range(1, len(values) + 1)):
            raise PackageError(f"child order is not consecutive: {parent}")


def _validate_metadata(card: dict, path: str) -> None:
    required = {"spec", "id", "kind", "title", "description"}
    allowed = required | {
        "order",
        "source",
        "content",
        "assets",
        "warnings",
        "table",
    }
    if not required <= card.keys() or card["spec"] != "reindex/node@1.0":
        raise PackageError(f"missing or invalid Node metadata: {path}")
    if unknown := set(card) - allowed:
        raise PackageError(
            f"unknown Node fields in {path}: {', '.join(sorted(unknown))}"
        )
    try:
        UUID(str(card["id"]))
    except ValueError as error:
        raise PackageError(f"invalid Node UUID: {path}") from error
    if card["kind"] not in {"group", "text", "table", "image", "file"}:
        raise PackageError(f"invalid Node kind: {path}")
    if not all(
        isinstance(card[key], str) and card[key].strip()
        for key in ("title", "description")
    ):
        raise PackageError(f"title and description are required: {path}")
    if card["kind"] == "group" and "content" in card:
        raise PackageError(f"group cannot contain content: {path}")
    if card["kind"] != "group" and "content" not in card:
        raise PackageError(f"non-group requires content: {path}")
    warnings = card.get("warnings", [])
    if not isinstance(warnings, list) or any(
        not isinstance(value, str) or not value for value in warnings
    ):
        raise PackageError(f"warnings must be non-empty strings: {path}")


def _validate_resources(
    package: Path, raw_root: Path, card_path: str, card: dict, used: set[str]
) -> None:
    references = []
    if source := card.get("source"):
        references.append(("source", source))
    if content := card.get("content"):
        references.append(("content", content))
    references.extend(
        (f"asset {index}", value)
        for index, value in enumerate(card.get("assets", []), 1)
    )
    for role, value in references:
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("uri"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", str(value.get("sha256", "")))
        ):
            raise PackageError(f"invalid {role} reference: {card_path}")
        uri = value["uri"]
        if uri.startswith("raw://"):
            relative = _safe(uri.removeprefix("raw://"))
            file = raw_root / relative
        elif uri.startswith("./") and role != "source":
            relative = _safe(
                (PurePosixPath(card_path).parent / uri.removeprefix("./")).as_posix()
            )
            file = package / relative
            used.add(relative)
        else:
            raise PackageError(f"unsupported {role} URI: {card_path}")
        if not file.is_file() or sha256_file(file) != value["sha256"]:
            raise PackageError(f"missing or mismatched {role}: {card_path}")
        if role != "source" and not isinstance(value.get("media_type"), str):
            raise PackageError(f"media_type is required for {role}: {card_path}")
    for index, asset in enumerate(card.get("assets", []), 1):
        if not re.search(
            rf"\.assets{index:03d}\.[^.]+$", PurePosixPath(asset["uri"]).name
        ):
            raise PackageError(f"asset ordinal mismatch: {card_path}")
        if not all(
            isinstance(asset.get(key), str) and asset[key]
            for key in ("media_type", "role", "description")
        ):
            raise PackageError(f"invalid asset metadata: {card_path}")


def _validate_table(package: Path, card_path: str, card: dict) -> None:
    table = card.get("table")
    if not isinstance(table, dict):
        raise PackageError(f"table metadata required: {card_path}")
    uri = card["content"]["uri"]
    if not uri.startswith("./") or not uri.endswith(".csv"):
        raise PackageError(f"table content must be package CSV: {card_path}")
    file = package / _safe((PurePosixPath(card_path).parent / uri[2:]).as_posix())
    with file.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))
    if not rows or not rows[0] or len(rows[0]) != len(set(rows[0])):
        raise PackageError(f"invalid CSV header: {card_path}")
    headers, data = rows[0], rows[1:]
    if any(len(row) != len(headers) for row in data) or table.get("row_count") != len(
        data
    ):
        raise PackageError(f"CSV shape mismatch: {card_path}")
    columns = table.get("columns")
    if (
        not isinstance(columns, list)
        or [value.get("name") for value in columns if isinstance(value, dict)]
        != headers
    ):
        raise PackageError(f"table columns mismatch: {card_path}")
    primary = table.get("primary_key", [])
    if not isinstance(primary, list) or any(name not in headers for name in primary):
        raise PackageError(f"invalid table primary key: {card_path}")


def _parent_card(path: str) -> str:
    value = PurePosixPath(path)
    return (
        (value.parent.parent if value.name == "index.node.md" else value.parent)
        / "index.node.md"
    ).as_posix()


def _safe(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise PackageError(f"unsafe resource path: {value}")
    return path.as_posix()
