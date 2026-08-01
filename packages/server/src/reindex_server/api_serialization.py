from __future__ import annotations

from urllib.parse import quote

from fastapi.responses import StreamingResponse

from reindex_server.contracts import SearchRequest


def node_json(node, include_detail: bool = False) -> dict:
    value = {
        "id": node.id,
        "path": node.path,
        "parent_id": node.parent_id,
        "order": node.order,
        "depth": len(node.tree_path) - 1,
        "kind": node.kind,
        "title": node.title,
        "description": node.description,
    }
    if include_detail:
        value.update(
            {
                "card_markdown": node.card_markdown,
                "attributes": node.attributes,
                "node_hash": node.node_hash,
                "resources": [_resource_json(link) for link in node.resources],
            }
        )
    return value


def resource_download(store, resource, disposition: str) -> StreamingResponse:
    stream = store.open(resource.object_key)

    def chunks():
        try:
            while chunk := stream.read(1024 * 1024):
                yield chunk
        finally:
            stream.close()

    filename = quote(resource.display_name)
    headers = {"Content-Disposition": f"{disposition}; filename*=UTF-8''{filename}"}
    return StreamingResponse(chunks(), media_type=resource.media_type, headers=headers)


def search_response(
    service, collection_id: str, response, request: SearchRequest | None = None
) -> dict:
    value = {
        "executed_mode": response.executed_mode,
        "embedding_profile": response.embedding_profile,
        "candidate_count": response.candidate_count,
        "next_cursor": response.next_cursor,
        "results": [
            _result(service, collection_id, hit, rank)
            for rank, hit in enumerate(response.results, response.result_offset + 1)
        ],
    }
    if request:
        value["applied"] = {
            "candidate_limit": request.candidate_limit,
            "filters": request.filters.model_dump(mode="json"),
            "ranking": request.ranking.model_dump(),
        }
    if response.reranker_profile:
        value["reranking"] = {
            "profile": response.reranker_profile,
            "candidate_limit": service.reranker.candidate_limit,
            "reranked_count": response.reranked_count,
            "latency_ms": response.rerank_latency_ms,
            "fusion": "weighted_rrf",
            "weight": response.rerank_fusion_weight,
            "rrf_k": response.rerank_rrf_k,
        }
    return value


def _resource_json(link) -> dict:
    resource = link.resource
    return {
        "role": link.role,
        "ordinal": link.ordinal,
        "resource_id": resource.id,
        "namespace": resource.namespace,
        "logical_path": resource.logical_path,
        "display_name": resource.display_name,
        "media_type": resource.media_type,
        "sha256": resource.sha256,
        "byte_size": resource.byte_size,
        "locator": link.locator,
        "asset_role": link.asset_role,
        "description": link.description,
    }


def _result(service, collection_id: str, hit, rank: int) -> dict:
    unit = hit.unit
    node = service.get_node(collection_id, unit.node_id)
    return {
        "rank": rank,
        "score": hit.score,
        "channels": list(hit.channels),
        "ranks": hit.ranks,
        "scores": {
            "bm25": hit.bm25_score,
            "semantic": hit.semantic_score,
            "rerank": hit.rerank_score,
            "rerank_bonus": hit.rerank_bonus,
        },
        "evidence": {
            "node_id": node.id,
            "path": node.path,
            "parent_id": node.parent_id,
            "kind": node.kind,
            "title": node.title,
            "description": node.description,
            "unit_type": unit.unit_type,
            "resource_id": unit.resource_id,
            "excerpt": unit.original_text,
            "row": unit.row,
            "line_start": unit.start_line,
            "line_end": unit.end_line,
            "chunk_ordinal": unit.ordinal,
            "locator": unit.locator or node.locator,
        },
    }
