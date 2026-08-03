from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from reindex_cli.package.cards import machine_hash, parse_card, render_card
from reindex_cli.pipeline.assembly import ROOT_KEY
from reindex_cli.pipeline.models import BuildState, DraftNode
from reindex_cli.util import load_json, sha256_bytes


def render_package(state: BuildState) -> Path:
    staging_root = state.context.root / ".rei" / "staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix="package-", dir=staging_root))
    previous = load_json(state.context.root / ".rei" / "build.json", {})
    previous_nodes = previous.get("nodes", {}) if isinstance(previous, dict) else {}
    drafts = {node.logical_key: node for node in state.drafts}
    children = _children(state.drafts)
    records: dict[str, dict[str, Any]] = {}
    state.staging = target
    try:
        _render_node(
            state,
            drafts[ROOT_KEY],
            target,
            None,
            False,
            children,
            previous_nodes,
            records,
        )
    except Exception:
        shutil.rmtree(target)
        raise
    state.node_records = records
    return target


def _render_node(
    state: BuildState,
    node: DraftNode,
    directory: Path,
    order: int | None,
    numbered: bool,
    children: dict[str, list[DraftNode]],
    previous: dict[str, Any],
    records: dict[str, dict[str, Any]],
) -> None:
    from reindex_cli.util import slugify

    node_id = state.identities[node.logical_key]
    if node.kind == "group":
        node_dir = (
            directory
            if node.logical_key == ROOT_KEY
            else directory / slugify(node.title, "group")
        )
        node_dir.mkdir(parents=True, exist_ok=True)
        card_path = node_dir / "index.node.md"
        stem = None
    else:
        slug = slugify(node.title)
        stem = f"{order:05d}--{slug}" if numbered else slug
        node_dir = directory
        node_dir.mkdir(parents=True, exist_ok=True)
        card_path = node_dir / f"{stem}.node.md"
    metadata = _metadata(node, node_id, order, node_dir, stem)
    body, curated = _body(state, node, node_id, previous)
    card_path.write_bytes(render_card(metadata, body))
    relative_card = card_path.relative_to(state.staging).as_posix()
    records[node_id] = {
        "logical_key": node.logical_key,
        "card_path": relative_card,
        "generated_body_sha256": sha256_bytes(node.body.encode()),
        "published_body_sha256": sha256_bytes(body.encode()),
        "machine_sha256": machine_hash(metadata),
        "source_sha256": node.source_sha256,
        "curated": curated,
    }
    ordered = children.get(node.logical_key, [])
    for child_order, child in enumerate(ordered, 1):
        _render_node(
            state,
            child,
            node_dir,
            child_order,
            node.logical_key != ROOT_KEY,
            children,
            previous,
            records,
        )


def _metadata(
    node: DraftNode, node_id: str, order: int | None, directory: Path, stem: str | None
) -> dict:
    from reindex_cli.util import sha256_bytes

    value: dict[str, Any] = {
        "spec": "reindex/node@1.0",
        "id": node_id,
        "kind": node.kind,
    }
    if order is not None:
        value["order"] = order
    value.update({"title": node.title, "description": node.description})
    if node.source_path:
        source: dict[str, Any] = {
            "uri": f"raw://{node.source_path}",
            "sha256": node.source_sha256,
        }
        if node.pages:
            source["locator"] = {"pages": list(node.pages)}
        value["source"] = source
    if node.kind != "group":
        assert stem and node.content is not None and node.extension and node.media_type
        content_name = f"{stem}.{node.extension}"
        (directory / content_name).write_bytes(node.content)
        value["content"] = {
            "uri": f"./{content_name}",
            "media_type": node.media_type,
            "sha256": sha256_bytes(node.content),
        }
    if node.assets:
        assets = []
        for index, asset in enumerate(node.assets, 1):
            name = f"{stem}.assets{index:03d}.{asset.extension}"
            (directory / name).write_bytes(asset.content)
            assets.append(
                {
                    "uri": f"./{name}",
                    "media_type": asset.media_type,
                    "sha256": sha256_bytes(asset.content),
                    "role": asset.role,
                    "description": asset.description,
                }
            )
        value["assets"] = assets
    if node.table:
        value["table"] = {
            key: item
            for key, item in node.table.items()
            if key not in {"preview", "profile"}
        }
    if node.warnings:
        value["warnings"] = node.warnings
    return value


def _body(
    state: BuildState, node: DraftNode, node_id: str, previous: dict[str, Any]
) -> tuple[str, bool]:
    record = previous.get(node_id)
    if not isinstance(record, dict):
        return node.body, False
    card_relative = record.get("card_path")
    if not isinstance(card_relative, str):
        return node.body, False
    card_path = state.context.output_dir / card_relative
    if not card_path.is_file():
        return node.body, False
    _metadata_value, body = parse_card(card_path)
    generated = record.get("generated_body_sha256")
    if generated and sha256_bytes(body.encode()) != generated:
        if record.get("source_sha256") != node.source_sha256:
            state.warnings.append(
                f"Agent card requires review after source change: {node.title}"
            )
            state.review_required.append(node_id)
        return body, True
    return node.body, False


def _children(nodes: list[DraftNode]) -> dict[str, list[DraftNode]]:
    result: dict[str, list[DraftNode]] = {}
    for node in nodes:
        if node.parent_key is not None:
            result.setdefault(node.parent_key, []).append(node)
    for values in result.values():
        values.sort(
            key=lambda node: (
                node.order_hint,
                node.item_path,
                node.kind,
                node.title,
                node.logical_key,
            )
        )
    return result
