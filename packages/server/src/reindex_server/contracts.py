from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from reindex_server.request_contract_base import (
    ApiRequest,
    CollectionRequest,
    NodeRequest,
)


class VersionedCollectionRequest(CollectionRequest):
    version_id: UUID | None = None

    @property
    def version_key(self) -> str | None:
        return str(self.version_id) if self.version_id else None


class GetRequest(CollectionRequest):
    version_id: UUID | None = None
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


class TransportFile(ApiRequest):
    namespace: Literal["raw", "package"]
    logical_path: str = Field(min_length=1, max_length=2000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(ge=0)
    media_type: str = Field(min_length=1, max_length=255)

    @field_validator("logical_path")
    @classmethod
    def validate_logical_path(cls, value: str) -> str:
        from reindex_server.domain import safe_relative_path

        return safe_relative_path(value).as_posix()


class TransportManifest(ApiRequest):
    spec: Literal["reindex/transport@1.0"]
    package_root: str = Field(min_length=1, max_length=255)
    files: list[TransportFile] = Field(min_length=1, max_length=100000)

    @field_validator("package_root")
    @classmethod
    def validate_package_root(cls, value: str) -> str:
        if "/" in value or "\\" in value or value in {".", ".."}:
            raise ValueError("package_root must be one safe directory name")
        return value

    @model_validator(mode="after")
    def validate_files(self) -> TransportManifest:
        keys = [(item.namespace, item.logical_path) for item in self.files]
        if len(keys) != len(set(keys)):
            raise ValueError("manifest contains duplicate namespace/logical_path")
        sizes: dict[str, int] = {}
        for item in self.files:
            previous = sizes.setdefault(item.sha256, item.byte_size)
            if previous != item.byte_size:
                raise ValueError("same blob hash has conflicting byte_size")
        return self


class PushRequest(ApiRequest):
    name: str = Field(min_length=1, max_length=80)
    collection_id: UUID
    base_version_id: UUID | None = None
    message: str = Field(default="Publish Collection", min_length=1, max_length=1000)
    operation: Literal["publish", "rollback"] = "publish"
    source_version_id: UUID | None = None
    dry_run: bool = False
    manifest: TransportManifest

    @model_validator(mode="after")
    def validate_operation(self) -> PushRequest:
        if self.operation == "rollback" and self.source_version_id is None:
            raise ValueError("rollback requires source_version_id")
        if self.operation == "publish" and self.source_version_id is not None:
            raise ValueError("source_version_id is only valid for rollback")
        return self


class CommitRequest(ApiRequest):
    upload_id: UUID


class FetchRequest(CollectionRequest):
    version_id: UUID | None = None

    @property
    def version_key(self) -> str | None:
        return str(self.version_id) if self.version_id else None


class HistoryRequest(CollectionRequest):
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=100)


class BrowseRequest(CollectionRequest):
    parent_node_id: UUID | None = Field(
        default=None, description="Parent Node UUID; null selects the full Collection."
    )
    recursive: bool = Field(
        default=False,
        description="Return all descendants instead of only direct children.",
    )


from reindex_server.search_contracts import (  # noqa: E402
    GrepRequest,
    SearchFilters,
    SearchRanking,
    SearchRequest,
    TableQueryRequest,
)
