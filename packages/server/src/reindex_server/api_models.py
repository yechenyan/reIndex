from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from reindex_server.contracts import SearchFilters, SearchRanking


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


class ImportAcceptedResponse(BaseModel):
    collection_id: str
    status: Literal["queued"]


class CollectionStatusResponse(BaseModel):
    collection_id: str
    root_node_id: str
    status: Literal["draft", "queued", "validating", "indexing", "ready", "failed"]
    active_revision_id: str | None
    embedding_profile: str | None
    progress: dict[str, Any]
    error: dict[str, Any] | None


class RawUploadResponse(BaseModel):
    collection_id: str
    raw_path: str
    sha256: str


class NodeSummary(BaseModel):
    id: str
    path: str
    parent_id: str | None
    kind: Literal["group", "text", "table", "image"]
    title: str
    description: str
    locator: dict[str, Any] | None


class NodeDetail(NodeSummary):
    body: str
    source_uri: str | None
    resource_uri: str | None
    table: dict[str, Any] | None


class BrowseResponse(BaseModel):
    nodes: list[NodeSummary]


class TableQueryResponse(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    truncated: bool


class ComponentScores(BaseModel):
    bm25: float | None = None
    semantic: float | None = None
    rerank: float | None = None
    rerank_bonus: float | None = None


class Evidence(BaseModel):
    node_id: str
    path: str
    parent_id: str | None
    kind: Literal["group", "text", "table", "image"]
    title: str
    description: str
    locator: dict[str, Any] | None = None
    excerpt: str
    source_sha256: str | None = None
    row: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    chunk_ordinal: int


class SearchResult(BaseModel):
    rank: int = Field(ge=1)
    score: float
    channels: list[Literal["lexical", "semantic", "grep"]]
    ranks: dict[str, int]
    scores: ComponentScores
    evidence: Evidence


class AppliedSearch(BaseModel):
    candidate_limit: int
    filters: SearchFilters
    ranking: SearchRanking


class AppliedReranking(BaseModel):
    profile: str
    candidate_limit: int = Field(ge=1)
    reranked_count: int = Field(ge=0)
    latency_ms: float = Field(ge=0)
    fusion: Literal["weighted_rrf"]
    weight: float = Field(ge=0)
    rrf_k: int = Field(ge=1)


class SearchApiResponse(BaseModel):
    executed_mode: Literal["lexical", "semantic", "hybrid", "grep"]
    embedding_profile: str | None
    revision_id: str
    candidate_count: int = Field(ge=0)
    next_cursor: str | None
    results: list[SearchResult]
    applied: AppliedSearch | None = None
    reranking: AppliedReranking | None = None


ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Invalid request or cursor."},
    404: {"model": ErrorResponse, "description": "Collection or resource not found."},
    409: {"model": ErrorResponse, "description": "Collection or model state conflict."},
    422: {"model": ErrorResponse, "description": "Request schema validation failed."},
    500: {"model": ErrorResponse, "description": "Unexpected server error."},
}
