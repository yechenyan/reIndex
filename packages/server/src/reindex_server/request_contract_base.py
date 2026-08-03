from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CollectionRequest(ApiRequest):
    collection: str = Field(
        min_length=1, max_length=80, description="User-facing Collection name."
    )

    @property
    def collection_key(self) -> str:
        return self.collection


class NodeRequest(CollectionRequest):
    node_id: UUID = Field(description="Node UUID in the current Collection state.")

    @property
    def node_key(self) -> str:
        return str(self.node_id)
