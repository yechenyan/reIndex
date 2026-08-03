from __future__ import annotations

from reindex_cli.parsers.common import description_for, initial_body
from reindex_cli.parsers.registry import parse_item, parser_cache_key
from reindex_cli.pipeline.models import (
    BuildState,
    DraftNode,
    SourceItem,
    artifact_from_json,
    artifact_to_json,
)
from reindex_cli.pipeline.planning import external_table_pages
from reindex_cli.util import atomic_json, load_json


def parse_active_items(state: BuildState) -> None:
    cache_root = state.context.root / ".rei" / "cache" / "parse"
    for relative in sorted(state.active_paths):
        item = state.discovered[relative]
        excluded = (
            external_table_pages(relative, state.discovered)
            if item.path.suffix.lower() == ".pdf"
            else set()
        )
        key = parser_cache_key(item, excluded)
        cache_path = cache_root / f"{key}.json"
        cached = load_json(cache_path, None)
        if isinstance(cached, dict) and cached.get("spec") == "reindex/parse-cache@1.0":
            nodes = artifact_from_json(cached)
            state.cache_hits += 1
        else:
            nodes = parse_item(item, excluded)
            atomic_json(cache_path, artifact_to_json(nodes))
            state.parsed_items += 1
        if any(
            candidate.config.part_of == relative
            for candidate in state.discovered.values()
        ):
            nodes = _as_document_group(item, nodes)
        state.drafts.extend(nodes)


def _as_document_group(item: SourceItem, nodes: list[DraftNode]) -> list[DraftNode]:
    if any(
        node.logical_key == item.relative and node.kind == "group" for node in nodes
    ):
        return nodes
    anchor = next((node for node in nodes if node.logical_key == item.relative), None)
    if anchor is None:
        return nodes
    anchor.logical_key = f"{item.relative}#content"
    anchor.parent_key = item.relative
    group = DraftNode(
        logical_key=item.relative,
        item_path=item.relative,
        kind="group",
        title=anchor.title,
        description=item.config.description or description_for(anchor.title, "group"),
        source_path=item.relative,
        source_sha256=item.sha256,
    )
    group.body = initial_body(group)
    return [group, *nodes]
