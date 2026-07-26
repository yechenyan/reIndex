from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CollectionRequest(BaseModel):
    collection_id: str


class DownloadRawRequest(CollectionRequest):
    raw_path: str
    disposition: Literal["inline", "attachment"] = "attachment"


class NodeRequest(CollectionRequest):
    node_id: str


class DownloadNodeRequest(NodeRequest):
    target: Literal["source", "resource"]
    disposition: Literal["inline", "attachment"] = "attachment"


class BrowseRequest(CollectionRequest):
    parent_node_id: str | None = None


class SearchRequest(CollectionRequest):
    query: str = Field(min_length=1, max_length=1000)
    mode: Literal["lexical", "semantic", "hybrid", "auto"] = "auto"
    limit: int = Field(default=10, ge=1, le=50)


class GrepRequest(SearchRequest):
    mode: Literal["lexical"] = "lexical"


class TableQueryRequest(NodeRequest):
    sql: str = Field(min_length=1, max_length=10_000)
    params: list[str | int | float | bool | None] = Field(default_factory=list)
