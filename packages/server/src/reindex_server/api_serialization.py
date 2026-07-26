from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse

from reindex_server.contracts import SearchRequest


def node_json(node, include_body: bool = False) -> dict:
    value = {
        "id": node.id,
        "path": node.path,
        "parent_id": node.parent_id,
        "kind": node.kind,
        "title": node.title,
        "description": node.description,
        "locator": node.locator,
    }
    if include_body:
        value.update(
            {
                "body": node.body,
                "source_uri": node.source_uri,
                "resource_uri": node.resource_uri,
                "table": node.table,
            }
        )
    return value


def search_response(
    service, collection_id: str, response, request: SearchRequest | None = None
) -> dict:
    value = {
        "executed_mode": response.executed_mode,
        "embedding_profile": response.embedding_profile,
        "revision_id": response.revision_id,
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
    return value


def download(path: Path, disposition: str) -> FileResponse:
    return FileResponse(path, filename=path.name, content_disposition_type=disposition)


def _result(service, collection_id: str, hit, rank: int) -> dict:
    unit = hit.unit
    node = service.get_node(collection_id, unit.node_id)
    evidence = node_json(node)
    evidence["node_id"] = evidence.pop("id")
    return {
        "rank": rank,
        "score": hit.score,
        "channels": list(hit.channels),
        "ranks": hit.ranks,
        "scores": {"bm25": hit.bm25_score, "semantic": hit.semantic_score},
        "evidence": {
            **evidence,
            "excerpt": unit.original_text,
            "source_sha256": node.source_sha256,
            "row": unit.row,
            "line_start": unit.start_line,
            "line_end": unit.end_line,
            "chunk_ordinal": unit.ordinal,
            "locator": unit.locator or node.locator,
        },
    }
