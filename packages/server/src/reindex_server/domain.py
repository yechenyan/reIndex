from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4


@dataclass
class Node:
    id: str
    path: str
    parent_id: str | None
    kind: str
    title: str
    description: str
    body: str
    source_uri: str | None
    source_sha256: str | None
    locator: dict | None
    resource_uri: str | None
    resource_key: str | None
    table: dict | None


@dataclass
class SearchUnit:
    node_id: str
    text: str
    excerpt: str
    row: int | None = None
    embedding: list[float] | None = None


@dataclass
class Collection:
    id: str
    root_node: Node
    status: str = "draft"
    active_revision: str | None = None
    progress: dict = field(default_factory=dict)
    error: dict | None = None
    raw: dict[str, str] = field(default_factory=dict)
    nodes: dict[str, Node] = field(default_factory=dict)
    units: list[SearchUnit] = field(default_factory=list)

    @classmethod
    def create(cls, root_node: Node) -> "Collection":
        return cls(id=root_node.id, root_node=root_node, nodes={root_node.id: root_node})

    def begin_import(self) -> str:
        if self.status in {"queued", "validating", "indexing"}:
            raise ValueError("collection already has an import in progress")
        self.status, self.error = "queued", None
        self.progress = {"stage": "queued", "completed": 0, "total": 0}
        return str(uuid4())

    def status_response(self) -> dict:
        return {
            "collection_id": self.id,
            "root_node_id": self.root_node.id,
            "status": self.status,
            "active_revision_id": self.active_revision,
            "progress": self.progress,
            "error": self.error,
        }


def node_from_frontmatter(path: str, metadata: dict, body: str, parent_id: str | None) -> Node:
    source = metadata.get("source") or {}
    resource = metadata.get("resource") or {}
    return Node(
        id=metadata["id"],
        path=path,
        parent_id=parent_id,
        kind=metadata["kind"],
        title=metadata["title"],
        description=metadata["description"],
        body=body,
        source_uri=source.get("uri"),
        source_sha256=source.get("sha256"),
        locator=source.get("locator"),
        resource_uri=resource.get("uri"),
        resource_key=None,
        table=metadata.get("table"),
    )


def safe_relative_path(value: str) -> Path:
    path = Path(value)
    if not value or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("path must be a non-empty relative path without traversal")
    return path
