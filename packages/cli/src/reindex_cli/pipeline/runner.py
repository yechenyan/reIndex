from __future__ import annotations

import shutil
from pathlib import Path

from reindex_cli.collection.resolver import CollectionContext
from reindex_cli.manifest.parser import load_manifest
from reindex_cli.package import render_package, validate_package
from reindex_cli.pipeline.assembly import assemble_nodes, identity_state
from reindex_cli.pipeline.discovery import discover
from reindex_cli.pipeline.inspection import (
    has_input_changes,
    input_changes,
    inspect_items,
)
from reindex_cli.pipeline.models import BuildState
from reindex_cli.pipeline.parsing import parse_active_items
from reindex_cli.pipeline.planning import active_paths
from reindex_cli.pipeline.publish import publish
from reindex_cli.util import atomic_json, load_json


def inspect_collection(context: CollectionContext) -> dict:
    manifest = load_manifest(context.root)
    discovered = discover(context.root, manifest)
    previous = load_json(context.root / ".rei" / "build.json", {})
    selected = active_paths(
        context.root, context.scope_relative, discovered, previous, manifest
    )
    changes = input_changes(manifest, discovered, selected, previous)
    items, ignored = inspect_items(manifest, discovered, selected, previous)
    counts: dict[str, int] = {}
    for relative in selected:
        suffix = Path(relative).suffix.lower().lstrip(".") or "file"
        counts[suffix] = counts.get(suffix, 0) + 1
    relations = sum(
        bool(item.part_of or item.derived_from) for item in manifest.items.values()
    )
    return {
        "status": "ready",
        "collection_root": str(context.root),
        "collection_id": context.collection_id,
        "scope": context.scope_relative,
        "manifest": {
            "path": str(manifest.path) if manifest.path else None,
            "valid": True,
        },
        "inputs": counts,
        "relations": relations,
        "summary": {
            "selected": len(selected),
            "ignored": len(ignored),
            "new": len(changes["new_inputs"]),
            "changed": len(changes["changed_inputs"]),
            "removed": len(changes["removed_inputs"]),
        },
        "items": items,
        "ignored_items": ignored,
        "changes": changes,
        "findings": [],
        "output": str(context.output_dir),
    }


def run_scan(context: CollectionContext) -> dict:
    state = BuildState(context)
    state.manifest = load_manifest(context.root)
    state.discovered = discover(context.root, state.manifest)
    previous = load_json(context.root / ".rei" / "build.json", {})
    state.active_paths = active_paths(
        context.root,
        context.scope_relative,
        state.discovered,
        previous,
        state.manifest,
    )
    parse_active_items(state)
    assemble_nodes(state)
    staging = render_package(state)
    try:
        validation = validate_package(staging, context.root, context.collection_id)
        if validation["nodes"] != len(state.drafts):
            raise ValueError("Rendered package lost or collided Node paths")
        publish(staging, context.output_dir, context.root / ".rei")
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    report = _build_report(state, validation, previous)
    atomic_json(context.root / ".rei" / "identities.json", identity_state(state))
    atomic_json(context.root / ".rei" / "build.json", report)
    return {
        "status": "valid",
        "collection_id": context.collection_id,
        "package": str(context.output_dir),
        "nodes": validation["nodes"],
        "changes": report["changes"],
        "review": report["review"],
        "warnings": report["warnings"],
        "warning_count": len(report["warnings"]),
        "parsed": state.parsed_items,
        "cached": state.cache_hits,
    }


def check_collection(context: CollectionContext) -> dict:
    report = load_json(context.root / ".rei" / "build.json", None)
    if not isinstance(report, dict) or report.get("status") != "valid":
        raise ValueError("No successful build state found; run rei scan first")
    validation = validate_package(
        context.output_dir,
        context.root,
        context.collection_id,
        report.get("nodes", {}),
    )
    manifest = load_manifest(context.root)
    discovered = discover(context.root, manifest)
    selected = active_paths(context.root, ".", discovered, report, manifest)
    stale = input_changes(manifest, discovered, selected, report)
    return {
        "status": "stale" if has_input_changes(stale) else "valid",
        "package": str(context.output_dir),
        "nodes": validation["nodes"],
        "agent_modified_cards": _agent_edits(context, report),
        "stale_inputs": has_input_changes(stale),
        "stale": stale,
    }


def _build_report(state: BuildState, validation: dict, previous: dict) -> dict:
    assert state.manifest is not None
    old_nodes = previous.get("nodes", {}) if isinstance(previous, dict) else {}
    new_ids = set(state.node_records)
    old_ids = set(old_nodes)
    changed = sorted(
        node_id
        for node_id in new_ids & old_ids
        if state.node_records[node_id].get("machine_sha256")
        != old_nodes[node_id].get("machine_sha256")
    )
    added = sorted(new_ids - old_ids)
    changes = {
        "added": added,
        "changed": changed,
        "removed": sorted(old_ids - new_ids),
    }
    review = {
        "new_nodes": added,
        "curated_nodes_affected": sorted(set(state.review_required)),
        "quality_findings": [],
    }
    return {
        "spec": "reindex/build@1.0",
        "status": "valid",
        "collection_id": state.context.collection_id,
        "package": state.context.output_dir.relative_to(state.context.root).as_posix(),
        "manifest_sha256": state.manifest.sha256,
        "item_paths": sorted(state.active_paths),
        "item_hashes": {
            path: state.discovered[path].sha256 for path in sorted(state.active_paths)
        },
        "nodes": state.node_records,
        "changes": changes,
        "review": review,
        "node_count": validation["nodes"],
        "warnings": state.warnings,
        "parsed_items": state.parsed_items,
        "cache_hits": state.cache_hits,
    }


def _agent_edits(context: CollectionContext, report: dict) -> int:
    from reindex_cli.package.cards import parse_card
    from reindex_cli.util import sha256_bytes

    count = 0
    for record in report.get("nodes", {}).values():
        path = context.output_dir / record["card_path"]
        _metadata, body = parse_card(path)
        if sha256_bytes(body.encode()) != record.get("generated_body_sha256"):
            count += 1
    return count
