from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from reindex_cli.collection.resolver import CollectionContext
from reindex_cli.manifest.models import InputManifest, ItemConfig


@dataclass(frozen=True)
class SourceItem:
    relative: str
    path: Path
    sha256: str
    media_type: str
    config: ItemConfig


@dataclass
class DraftAsset:
    content: bytes
    extension: str
    media_type: str
    role: str
    description: str


@dataclass
class DraftNode:
    logical_key: str
    item_path: str
    kind: str
    title: str
    description: str
    source_path: str | None = None
    source_sha256: str | None = None
    pages: tuple[int, int] | None = None
    content: bytes | None = None
    extension: str | None = None
    media_type: str | None = None
    body: str = ""
    table: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    assets: list[DraftAsset] = field(default_factory=list)
    parent_key: str | None = None
    order_hint: tuple[Any, ...] = field(default_factory=tuple)


@dataclass
class BuildState:
    context: CollectionContext
    manifest: InputManifest | None = None
    discovered: dict[str, SourceItem] = field(default_factory=dict)
    active_paths: set[str] = field(default_factory=set)
    drafts: list[DraftNode] = field(default_factory=list)
    identities: dict[str, str] = field(default_factory=dict)
    previous_identity_records: dict[str, dict[str, Any]] = field(default_factory=dict)
    moved_identity_keys: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)
    review_required: list[str] = field(default_factory=list)
    cache_hits: int = 0
    parsed_items: int = 0
    staging: Path | None = None
    node_records: dict[str, dict[str, Any]] = field(default_factory=dict)


def artifact_to_json(nodes: list[DraftNode]) -> dict[str, Any]:
    values = []
    for node in nodes:
        value = asdict(node)
        value["content"] = _encode(node.content)
        value["assets"] = [
            {**asdict(asset), "content": _encode(asset.content)}
            for asset in node.assets
        ]
        values.append(value)
    return {"spec": "reindex/parse-cache@1.0", "nodes": values}


def artifact_from_json(value: dict[str, Any]) -> list[DraftNode]:
    result = []
    for raw in value.get("nodes", []):
        raw = dict(raw)
        raw["content"] = _decode(raw.get("content"))
        raw["pages"] = tuple(raw["pages"]) if raw.get("pages") else None
        raw["order_hint"] = tuple(raw.get("order_hint", ()))
        raw["assets"] = [
            DraftAsset(**{**asset, "content": _decode(asset["content"])})
            for asset in raw.get("assets", [])
        ]
        result.append(DraftNode(**raw))
    return result


def _encode(value: bytes | None) -> str | None:
    return base64.b64encode(value).decode("ascii") if value is not None else None


def _decode(value: str | None) -> bytes | None:
    return base64.b64decode(value) if value is not None else None
