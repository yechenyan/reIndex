from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath


@dataclass(frozen=True)
class Resource:
    id: str
    collection_id: str
    namespace: str
    logical_path: str
    display_name: str
    sha256: str
    byte_size: int
    media_type: str
    object_key: str


@dataclass(frozen=True)
class NodeResource:
    role: str
    ordinal: int
    resource: Resource
    locator: dict | None = None
    asset_role: str | None = None
    description: str | None = None


@dataclass
class Node:
    id: str
    collection_id: str
    path: str
    parent_id: str | None
    order: int | None
    tree_path: tuple[str, ...]
    order_path: tuple[int, ...]
    kind: str
    title: str
    description: str
    card_markdown: str
    attributes: dict
    node_hash: str
    resources: list[NodeResource] = field(default_factory=list)

    def link(self, role: str, ordinal: int = 0) -> NodeResource | None:
        return next(
            (
                item
                for item in self.resources
                if item.role == role and item.ordinal == ordinal
            ),
            None,
        )

    @property
    def locator(self) -> dict | None:
        source = self.link("source")
        return source.locator if source else None


@dataclass
class SearchUnit:
    id: str
    node_id: str
    unit_type: str
    contextual_text: str
    original_text: str
    start_line: int | None
    end_line: int | None
    ordinal: int
    row: int | None = None
    locator: dict | None = None
    resource_id: str | None = None
    embedding: list[float] | None = None


@dataclass
class SearchHit:
    unit: SearchUnit
    score: float
    channels: tuple[str, ...]
    ranks: dict[str, int]
    bm25_score: float | None = None
    semantic_score: float | None = None
    rerank_score: float | None = None
    rerank_bonus: float | None = None


@dataclass
class SearchResponse:
    executed_mode: str
    embedding_profile: str | None
    results: list[SearchHit]
    result_offset: int = 0
    candidate_count: int = 0
    next_cursor: str | None = None
    reranker_profile: str | None = None
    reranked_count: int = 0
    rerank_latency_ms: float | None = None
    rerank_fusion_weight: float | None = None
    rerank_rrf_k: int | None = None


@dataclass(frozen=True)
class SearchOptions:
    query: str
    mode: str
    limit: int
    candidate_limit: int
    node_ids: tuple[str, ...] = ()
    kinds: tuple[str, ...] = ()
    path_prefix: str | None = None
    subtree_node_id: str | None = None
    lexical_weight: float = 0.5
    semantic_weight: float = 1.0
    rrf_k: int = 60
    max_per_node: int = 3
    semantic_threshold: float | None = None
    cursor: str | None = None


@dataclass
class Collection:
    id: str
    name: str
    status: str = "draft"
    package_hash: str | None = None
    embedding_profile: str | None = None
    progress: dict = field(default_factory=dict)
    error: dict | None = None
    resources: dict[tuple[str, str], Resource] = field(default_factory=dict)
    nodes: dict[str, Node] = field(default_factory=dict)
    units: list[SearchUnit] = field(default_factory=list)

    @property
    def root_node(self) -> Node:
        return self.nodes[self.id]

    def status_response(self) -> dict:
        return {
            "collection_id": self.id,
            "root_node_id": self.id,
            "status": self.status,
            "package_hash": self.package_hash,
            "embedding_profile": self.embedding_profile,
            "progress": self.progress,
            "error": self.error,
        }


def safe_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value
        or value.startswith("/")
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(
            "path must be a non-empty relative POSIX path without traversal"
        )
    return path
