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


class PushResponse(BaseModel):
    status: Literal["ready"]
    name: str
    collection_id: str
    package_hash: str
    nodes: int
    sources: int
    resources: int
    search_units: int
    embedding_profile: str | None


class PushStartResponse(BaseModel):
    status: Literal["upload", "ready", "planned"]
    upload_id: str | None = None
    expires_at: str | None = None
    head_version_id: str | None = None
    package_hash: str | None = None
    missing_blobs: list[dict[str, Any]]
    no_op: bool


class BlobUploadResponse(BaseModel):
    status: Literal["stored", "reused"]
    sha256: str
    byte_size: int


class VersionedPushResponse(PushResponse):
    version_id: str
    parent_version_id: str | None = None
    operation: Literal["publish", "rollback"]
    source_version_id: str | None = None
    uploaded_blobs: int
    reused_blobs: int
    embedded_units: int
    reused_embeddings: int
    no_op: bool = False


class FetchResponse(BaseModel):
    name: str
    collection_id: str
    version: dict[str, Any]
    manifest: dict[str, Any]


class HistoryResponse(BaseModel):
    name: str
    collection_id: str
    versions: list[dict[str, Any]]
    next_cursor: str | None = None


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
    kind: Literal["group", "text", "table", "image", "file"]
    title: str
    description: str
    unit_type: Literal["card", "content_text", "table_row"]
    resource_id: str | None = None
    locator: dict[str, Any] | None = None
    excerpt: str
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
    get: dict[str, Any]


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
