from __future__ import annotations

from dataclasses import replace

from reindex_server.domain import SearchHit, SearchOptions
from reindex_server.reranking import Reranker


def fuse_reranking(
    hits: list[SearchHit],
    reranked_hits: list[SearchHit],
    options: SearchOptions,
    reranker: Reranker,
) -> list[SearchHit]:
    if reranker.name == "disabled" or not hits:
        return hits
    original = {hit.unit.id: index for index, hit in enumerate(hits, 1)}
    rerank_position = {
        hit.unit.id: index
        for index, hit in enumerate(reranked_hits, 1)
        if hit.rerank_score is not None
    }
    rerank_score = {
        hit.unit.id: hit.rerank_score
        for hit in reranked_hits
        if hit.rerank_score is not None
    }
    bonus = confidence_bonus(reranked_hits)
    fused = []
    for hit in hits:
        ranks = dict(hit.ranks)
        score = sum(
            weight / (options.rrf_k + ranks[channel])
            for channel, weight in (
                ("lexical", options.lexical_weight),
                ("semantic", options.semantic_weight),
            )
            if channel in ranks
        )
        if not ranks:
            score = 1 / (options.rrf_k + original[hit.unit.id])
        if rank := rerank_position.get(hit.unit.id):
            ranks["rerank"] = rank
            score += reranker.fusion_weight / (options.rrf_k + rank)
        extra = bonus.get(hit.unit.id, 0.0)
        fused.append(
            replace(
                hit,
                score=score + extra,
                ranks=ranks,
                rerank_score=rerank_score.get(hit.unit.id),
                rerank_bonus=extra or None,
            )
        )
    return sorted(
        fused, key=lambda hit: (-hit.score, original[hit.unit.id], hit.unit.id)
    )


def confidence_bonus(reranked_hits: list[SearchHit]) -> dict[str, float]:
    scored = [hit for hit in reranked_hits if hit.rerank_score is not None]
    if len(scored) < 2:
        return {}
    first, second = scored[:2]
    margin = first.rerank_score - second.rerank_score
    if first.rerank_score <= 0 or margin <= 0.5:
        return {}
    return {first.unit.id: min(0.006, (margin - 0.5) * 0.003)}
