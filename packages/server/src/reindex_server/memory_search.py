from __future__ import annotations

import re

from reindex_server.domain import SearchHit


class MemorySearchBackend:
    """Small lexical backend for local development and end-to-end CLI tests."""

    def search(self, collection, options, query_embedding):
        terms = [value for value in options.query.casefold().split() if value]
        hits = []
        for unit in collection.units:
            if not _included(collection, unit, options):
                continue
            text = unit.contextual_text.casefold()
            matches = sum(text.count(term) for term in terms)
            if matches:
                hits.append(
                    SearchHit(
                        unit,
                        float(matches),
                        ("lexical",),
                        {"lexical": 0},
                        bm25_score=float(matches),
                    )
                )
        hits.sort(
            key=lambda value: (-value.score, value.unit.node_id, value.unit.ordinal)
        )
        for rank, hit in enumerate(hits, 1):
            hit.ranks["lexical"] = rank
        return hits[: options.candidate_limit]

    def grep(self, collection, pattern, limit, regex, case_sensitive):
        flags = 0 if case_sensitive else re.IGNORECASE
        expression = re.compile(pattern if regex else re.escape(pattern), flags)
        hits = []
        for unit in collection.units:
            if expression.search(unit.original_text):
                hits.append(SearchHit(unit, 1.0, ("grep",), {"grep": len(hits) + 1}))
                if len(hits) >= limit:
                    break
        return hits


def _included(collection, unit, options) -> bool:
    node = collection.nodes[unit.node_id]
    if options.node_ids and node.id not in options.node_ids:
        return False
    if options.kinds and node.kind not in options.kinds:
        return False
    if options.path_prefix and not node.path.startswith(options.path_prefix):
        return False
    return not (
        options.subtree_node_id and options.subtree_node_id not in node.tree_path
    )
