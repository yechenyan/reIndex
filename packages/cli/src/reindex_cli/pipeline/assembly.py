from __future__ import annotations

from pathlib import PurePosixPath
from uuid import uuid4

from reindex_cli.collection.state import identity_path
from reindex_cli.parsers.common import initial_body
from reindex_cli.pipeline.models import BuildState, DraftAsset, DraftNode
from reindex_cli.util import load_json

ROOT_KEY = "__collection__"


def assemble_nodes(state: BuildState) -> None:
    assert state.manifest is not None
    _attach_table_visuals(state)
    root = DraftNode(
        logical_key=ROOT_KEY,
        item_path="",
        kind="group",
        title=state.manifest.title,
        description=state.manifest.description,
    )
    root.body = initial_body(root)
    directories = _directory_nodes(state)
    state.drafts = [root, *directories, *state.drafts]
    _assign_parents(state)
    _fill_sources(state)
    _assign_identities(state)


def _directory_nodes(state: BuildState) -> list[DraftNode]:
    values: set[str] = set()
    for path in state.active_paths:
        parent = PurePosixPath(path).parent
        while parent.as_posix() != ".":
            values.add(parent.as_posix())
            parent = parent.parent
    result = []
    for path in sorted(values):
        config = state.manifest.items.get(path)
        title = (
            config.title
            if config and config.title
            else PurePosixPath(path).name.replace("-", " ").replace("_", " ").strip()
        )
        node = DraftNode(
            logical_key=f"dir:{path}",
            item_path=path,
            kind="group",
            title=title,
            description=(
                config.description
                if config and config.description
                else f"Files under {path}."
            ),
        )
        node.body = initial_body(node)
        result.append(node)
    return result


def _assign_parents(state: BuildState) -> None:
    for node in state.drafts:
        if node.logical_key == ROOT_KEY:
            node.parent_key = None
            continue
        if node.parent_key:
            continue
        if node.logical_key.startswith("dir:"):
            path = PurePosixPath(node.item_path).parent.as_posix()
            node.parent_key = f"dir:{path}" if path != "." else ROOT_KEY
            continue
        config = state.discovered[node.item_path].config
        if config.part_of:
            node.parent_key = config.part_of
        elif config.derived_from:
            node.parent_key = ROOT_KEY
        else:
            parent = PurePosixPath(node.item_path).parent.as_posix()
            node.parent_key = f"dir:{parent}" if parent != "." else ROOT_KEY


def _fill_sources(state: BuildState) -> None:
    for node in state.drafts:
        if node.source_path and not node.source_sha256:
            node.source_sha256 = state.discovered[node.source_path].sha256


def _assign_identities(state: BuildState) -> None:
    raw = load_json(identity_path(state.context.root), {"nodes": {}})
    previous = raw.get("nodes", raw.get("items", {})) if isinstance(raw, dict) else {}
    state.previous_identity_records = {
        key: value for key, value in previous.items() if isinstance(value, dict)
    }
    identities: dict[str, str] = {ROOT_KEY: state.context.collection_id}
    current_keys = {node.logical_key for node in state.drafts}
    for node in state.drafts:
        if node.logical_key == ROOT_KEY:
            continue
        record = previous.get(node.logical_key, {})
        node_id = record.get("id") if isinstance(record, dict) else None
        if not isinstance(node_id, str) and node.logical_key == node.item_path:
            candidates = [
                (key, value.get("id"))
                for key, value in previous.items()
                if key not in current_keys
                and "#" not in key
                and not key.startswith("dir:")
                and isinstance(value, dict)
                and value.get("source_sha256") == node.source_sha256
                and isinstance(value.get("id"), str)
            ]
            if len(candidates) == 1:
                old_key, node_id = candidates[0]
                state.moved_identity_keys.add(old_key)
        identities[node.logical_key] = (
            node_id if isinstance(node_id, str) else str(uuid4())
        )
    state.identities = identities


def identity_state(state: BuildState) -> dict:
    drafts = {node.logical_key: node for node in state.drafts}
    records = {
        key: value
        for key, value in state.previous_identity_records.items()
        if key not in state.moved_identity_keys
    }
    records.update(
        {
            key: {
                "id": node_id,
                "source_sha256": drafts[key].source_sha256,
            }
            for key, node_id in state.identities.items()
            if key != ROOT_KEY
        }
    )
    return {
        "spec": "reindex/node-identities@1.0",
        "nodes": records,
    }


def _attach_table_visuals(state: BuildState) -> None:
    tables = [
        node
        for node in state.drafts
        if node.kind == "table" and state.discovered[node.item_path].config.part_of
    ]
    images = [node for node in state.drafts if node.kind == "image"]
    consumed: set[str] = set()
    for table in tables:
        target = state.discovered[table.item_path].config.part_of
        if not table.pages:
            continue
        for image in images:
            if image.parent_key != target or not image.pages:
                continue
            if table.pages[0] <= image.pages[0] <= table.pages[1]:
                table.assets.append(
                    DraftAsset(
                        image.content or b"",
                        image.extension or "png",
                        image.media_type or "image/png",
                        "visual_reference",
                        f"PDF page {image.pages[0]} view associated with this external table.",
                    )
                )
                consumed.add(image.logical_key)
    state.drafts = [node for node in state.drafts if node.logical_key not in consumed]
