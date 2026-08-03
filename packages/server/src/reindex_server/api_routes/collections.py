from __future__ import annotations

from fastapi import FastAPI

from reindex_server.api_errors import http_error
from reindex_server.api_models import BrowseResponse, CollectionListResponse
from reindex_server.api_serialization import node_json
from reindex_server.contracts import BrowseRequest


def install_collection_routes(app: FastAPI) -> None:
    @app.get(
        "/v1/collections", response_model=CollectionListResponse, tags=["Collections"]
    )
    def list_collections() -> dict:
        return {
            "collections": [
                {
                    "name": item.name,
                    "collection_id": item.id,
                    "status": item.status,
                    "package_hash": item.package_hash,
                    "active_version_id": item.active_version_id,
                    "progress": {
                        key: value
                        for key, value in item.progress.items()
                        if key != "embedding_profile"
                    },
                }
                for item in app.state.service.list_collections()
            ]
        }

    @app.post("/v1/nodes/browse", response_model=BrowseResponse, tags=["Collections"])
    def browse_nodes(request: BrowseRequest) -> dict:
        try:
            resolved_id = app.state.service.resolve_collection(
                request.collection_key
            ).id
            return {
                "nodes": [
                    node_json(node)
                    for node in app.state.service.browse(
                        resolved_id,
                        str(request.parent_node_id) if request.parent_node_id else None,
                        request.recursive,
                    )
                ]
            }
        except Exception as error:
            raise http_error(error) from error
