from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from reindex_server.domain import SearchOptions


class ApiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CollectionRequest(ApiRequest):
    collection: str = Field(
        min_length=1, max_length=80, description="User-facing Collection name."
    )

    @property
    def collection_key(self) -> str:
        return self.collection


class GetRequest(CollectionRequest):
    node_id: UUID | None = None
    node_path: str | None = Field(default=None, min_length=1, max_length=1000)
    raw_uri: str | None = Field(default=None, min_length=7, max_length=1006)
    target: Literal["card", "source", "content", "asset"] = "content"
    asset_ordinal: int | None = Field(default=None, ge=1, le=999)

    @model_validator(mode="after")
    def validate_reference(self) -> GetRequest:
        references = sum(
            value is not None for value in (self.node_id, self.node_path, self.raw_uri)
        )
        if references != 1:
            raise ValueError("provide exactly one of node_id, node_path, or raw_uri")
        if self.raw_uri is not None and not self.raw_uri.startswith("raw://"):
            raise ValueError("raw_uri must start with raw://")
        if self.raw_uri is not None and self.asset_ordinal is not None:
            raise ValueError("asset_ordinal cannot be used with raw_uri")
        if self.target == "asset" and self.asset_ordinal is None:
            raise ValueError("asset_ordinal is required for asset")
        if self.target != "asset" and self.asset_ordinal is not None:
            raise ValueError("asset_ordinal is only valid for asset")
        return self


class NodeRequest(CollectionRequest):
    node_id: UUID = Field(description="Node UUID in the current Collection state.")

    @property
    def node_key(self) -> str:
        return str(self.node_id)


class SearchFilters(ApiRequest):
    node_ids: list[UUID] = Field(
        default_factory=list,
        max_length=100,
        description="Restrict retrieval to these Node UUIDs.",
    )
    kinds: list[Literal["group", "text", "table", "image", "file"]] = Field(
        default_factory=list,
        max_length=5,
        description="Restrict retrieval to these Node kinds.",
    )
    path_prefix: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="Restrict retrieval to Node paths with this prefix.",
    )
    subtree_node_id: UUID | None = Field(
        default=None, description="Restrict retrieval to this Node subtree."
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
                    "collection": "energy-reports",
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
            subtree_node_id=(
                str(self.filters.subtree_node_id)
                if self.filters.subtree_node_id
                else None
            ),
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
