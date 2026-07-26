from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from reindex_server.domain import SearchOptions


class ApiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CollectionRequest(ApiRequest):
    collection_id: UUID = Field(description="Collection root Node UUID.")

    @property
    def collection_key(self) -> str:
        return str(self.collection_id)


class DownloadRawRequest(CollectionRequest):
    raw_path: str = Field(
        min_length=1,
        max_length=1000,
        description="Collection-relative raw path without traversal.",
    )
    disposition: Literal["inline", "attachment"] = Field(
        default="attachment", description="Content-Disposition response mode."
    )


class NodeRequest(CollectionRequest):
    node_id: UUID = Field(description="Node UUID in the active revision.")

    @property
    def node_key(self) -> str:
        return str(self.node_id)


class DownloadNodeRequest(NodeRequest):
    target: Literal["source", "resource"]
    disposition: Literal["inline", "attachment"] = "attachment"


class BrowseRequest(CollectionRequest):
    parent_node_id: UUID | None = Field(
        default=None, description="Parent Node UUID; null selects collection roots."
    )


class SearchFilters(ApiRequest):
    node_ids: list[UUID] = Field(
        default_factory=list,
        max_length=100,
        description="Restrict retrieval to these Node UUIDs.",
    )
    kinds: list[Literal["group", "text", "table", "image"]] = Field(
        default_factory=list,
        max_length=4,
        description="Restrict retrieval to these Node kinds.",
    )
    path_prefix: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="Restrict retrieval to Node paths with this prefix.",
    )


class SearchRanking(ApiRequest):
    lexical_weight: float = Field(
        default=0.5, ge=0, le=10, description="BM25 rank weight in hybrid RRF."
    )
    semantic_weight: float = Field(
        default=1.0, ge=0, le=10, description="Vector rank weight in hybrid RRF."
    )
    rrf_k: int = Field(
        default=60,
        ge=1,
        le=200,
        description="RRF rank constant; lower values emphasize top ranks.",
    )
    max_per_node: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum diversified chunks returned from one Node.",
    )
    semantic_threshold: float | None = Field(
        default=None,
        ge=-1,
        le=1,
        description="Optional minimum cosine similarity for semantic candidates.",
    )


class SearchRequest(CollectionRequest):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "collection_id": "056e95b3-aad8-4740-af7e-973356ec4e44",
                    "query": "未来十年光伏装机容量会增长到多少？",
                    "mode": "hybrid",
                    "limit": 10,
                    "candidate_limit": 100,
                    "filters": {"kinds": ["text", "table"]},
                    "ranking": {
                        "lexical_weight": 0.5,
                        "semantic_weight": 1.0,
                        "rrf_k": 60,
                        "max_per_node": 3,
                    },
                }
            ]
        },
    )

    query: str = Field(
        min_length=1, max_length=1000, description="Natural-language search query."
    )
    mode: Literal["lexical", "semantic", "hybrid"] = Field(
        default="hybrid", description="Retrieval channels to execute."
    )
    limit: int = Field(
        default=10, ge=1, le=50, description="Maximum results in this page."
    )
    candidate_limit: int = Field(
        default=100,
        ge=10,
        le=500,
        description="Candidates retrieved per active channel before fusion.",
    )
    cursor: str | None = Field(
        default=None,
        min_length=1,
        max_length=2048,
        description="Opaque next_cursor returned by the previous identical search.",
    )
    filters: SearchFilters = Field(default_factory=SearchFilters)
    ranking: SearchRanking = Field(default_factory=SearchRanking)

    @field_validator("query")
    @classmethod
    def query_must_have_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must contain non-whitespace characters")
        return value

    @model_validator(mode="after")
    def validate_ranking(self) -> SearchRequest:
        if self.candidate_limit < self.limit:
            raise ValueError("candidate_limit must be greater than or equal to limit")
        if self.mode in {"lexical", "hybrid"} and self.ranking.lexical_weight == 0:
            raise ValueError(
                "lexical_weight must be positive for lexical or hybrid search"
            )
        if self.mode in {"semantic", "hybrid"} and self.ranking.semantic_weight == 0:
            raise ValueError(
                "semantic_weight must be positive for semantic or hybrid search"
            )
        return self

    def options(self) -> SearchOptions:
        return SearchOptions(
            query=self.query.strip(),
            mode=self.mode,
            limit=self.limit,
            candidate_limit=self.candidate_limit,
            node_ids=tuple(str(value) for value in self.filters.node_ids),
            kinds=tuple(self.filters.kinds),
            path_prefix=self.filters.path_prefix,
            lexical_weight=self.ranking.lexical_weight,
            semantic_weight=self.ranking.semantic_weight,
            rrf_k=self.ranking.rrf_k,
            max_per_node=self.ranking.max_per_node,
            semantic_threshold=self.ranking.semantic_threshold,
            cursor=self.cursor,
        )


class GrepRequest(CollectionRequest):
    pattern: str = Field(
        min_length=1, max_length=256, description="Literal text or PostgreSQL regex."
    )
    regex: bool = Field(default=False, description="Interpret pattern as a regex.")
    case_sensitive: bool = Field(
        default=False, description="Use case-sensitive matching."
    )
    limit: int = Field(default=10, ge=1, le=50, description="Maximum grep hits.")


class TableQueryRequest(NodeRequest):
    sql: str = Field(min_length=1, max_length=10_000)
    params: list[str | int | float | bool | None] = Field(default_factory=list)
