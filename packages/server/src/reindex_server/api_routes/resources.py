from __future__ import annotations

from fastapi import FastAPI, Response

from reindex_server.api_docs import RESOURCE_RESPONSES
from reindex_server.api_errors import http_error
from reindex_server.api_serialization import resource_download
from reindex_server.contracts import GetRequest


def install_resource_routes(app: FastAPI) -> None:
    @app.post(
        "/v1/get",
        response_class=Response,
        responses=RESOURCE_RESPONSES,
        tags=["Resources"],
    )
    def get_resource(request: GetRequest):
        try:
            resolved_id = app.state.service.resolve_collection(
                request.collection_key
            ).id
            snapshot = (
                app.state.service.version_snapshot(
                    request.collection_key, str(request.version_id)
                )
                if request.version_id
                else None
            )
            if request.raw_uri is not None:
                if snapshot:
                    resource = snapshot.resources[
                        ("raw", request.raw_uri.removeprefix("raw://"))
                    ]
                else:
                    resource = app.state.service.get_raw(
                        resolved_id, request.raw_uri.removeprefix("raw://")
                    )
            else:
                if snapshot:
                    node = (
                        snapshot.nodes[str(request.node_id)]
                        if request.node_id is not None
                        else _snapshot_node_by_path(
                            snapshot.nodes, str(request.node_path)
                        )
                    )
                else:
                    node = (
                        app.state.service.get_node(resolved_id, str(request.node_id))
                        if request.node_id is not None
                        else app.state.service.get_node_by_path(
                            resolved_id, str(request.node_path)
                        )
                    )
                link = node.link(request.target, request.asset_ordinal or 0)
                if link is None:
                    raise KeyError(f"Node has no {request.target} resource")
                resource = link.resource
            return resource_download(app.state.service.store, resource, "attachment")
        except Exception as error:
            raise http_error(error) from error


def _snapshot_node_by_path(nodes: dict, path: str):
    for node in nodes.values():
        if node.path == path:
            return node
    raise KeyError("node not found")
