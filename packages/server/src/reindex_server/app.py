from __future__ import annotations

import asyncio
import io
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from reindex_server import __version__
from reindex_server.api_errors import http_error, install_api_error_handling
from reindex_server.api_models import (
    ERROR_RESPONSES,
    BlobUploadResponse,
    FetchResponse,
    HealthResponse,
    HistoryResponse,
    PushStartResponse,
    SearchApiResponse,
    TableQueryResponse,
    VersionedPushResponse,
)
from reindex_server.api_serialization import resource_download, search_response
from reindex_server.contracts import (
    CommitRequest,
    FetchRequest,
    GetRequest,
    GrepRequest,
    HistoryRequest,
    PushRequest,
    SearchRequest,
    TableQueryRequest,
    VersionedCollectionRequest,
)
from reindex_server.runtime import service_from_environment
from reindex_server.service import ReindexService
from reindex_server.table_query import query_csv


def create_app(service: ReindexService | None = None) -> FastAPI:
    owned_database = None
    if service is None:
        service, owned_database = service_from_environment()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await asyncio.to_thread(service.warmup)
        yield
        if owned_database:
            owned_database.close()

    app = FastAPI(
        title="ReIndex API",
        version=__version__,
        lifespan=lifespan,
        responses=ERROR_RESPONSES,
    )
    app.state.service = service
    install_api_error_handling(app)

    def collection_id(name: str) -> str:
        return app.state.service.resolve_collection(name).id

    @app.get("/health", response_model=HealthResponse)
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.post("/v1/push", response_model=PushStartResponse)
    def push(request: PushRequest) -> dict:
        try:
            return app.state.service.start_push(request)
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/push/blob", response_model=BlobUploadResponse)
    async def push_blob(
        upload_id: Annotated[str, Form()],
        sha256: Annotated[str, Form()],
        blob: Annotated[UploadFile, File()],
    ) -> dict:
        try:
            with tempfile.TemporaryDirectory(prefix="reindex-api-blob-") as directory:
                path = Path(directory) / "blob"
                await _save_upload(blob, path)
                return await asyncio.to_thread(
                    app.state.service.upload_blob, upload_id, sha256, path
                )
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/push/commit", response_model=VersionedPushResponse)
    async def commit_push(request: CommitRequest) -> dict:
        try:
            return await asyncio.to_thread(
                app.state.service.commit_push, str(request.upload_id)
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/fetch", response_model=FetchResponse)
    def fetch(request: FetchRequest) -> dict:
        try:
            return app.state.service.fetch_version(
                request.collection_key, request.version_key
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/history", response_model=HistoryResponse)
    def history(request: HistoryRequest) -> dict:
        try:
            return app.state.service.history(
                request.collection_key, request.limit, request.cursor
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/pull")
    def pull(request: VersionedCollectionRequest):
        try:
            content, collection, version_id, package_hash = app.state.service.pull(
                request.collection_key, request.version_key
            )
            headers = {
                "Content-Disposition": (
                    f'attachment; filename="{collection.name}-nodes.zip"'
                ),
                "Content-Length": str(len(content)),
                "X-ReIndex-Package-Hash": package_hash,
                "X-ReIndex-Version-ID": version_id,
            }
            return StreamingResponse(
                io.BytesIO(content), media_type="application/zip", headers=headers
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/get")
    def get_resource(request: GetRequest):
        try:
            resolved_id = collection_id(request.collection_key)
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

    @app.post("/v1/search", response_model=SearchApiResponse)
    def search(request: SearchRequest) -> dict:
        try:
            response = app.state.service.search(
                collection_id(request.collection_key), request.options()
            )
            return search_response(
                app.state.service,
                collection_id(request.collection_key),
                response,
                request,
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/grep", response_model=SearchApiResponse)
    def grep(request: GrepRequest) -> dict:
        try:
            response = app.state.service.grep(
                collection_id(request.collection_key),
                request.pattern,
                request.limit,
                request.regex,
                request.case_sensitive,
            )
            return search_response(
                app.state.service, collection_id(request.collection_key), response
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/tables/query", response_model=TableQueryResponse)
    def query_table(request: TableQueryRequest) -> dict:
        try:
            node = app.state.service.get_node(
                collection_id(request.collection_key), request.node_key
            )
            content = node.link("content")
            if node.kind != "table" or not content:
                raise ValueError("node is not a queryable table")
            with app.state.service.store.materialize(
                content.resource.object_key
            ) as path:
                return query_csv(path, request.sql, request.params)
        except Exception as error:
            raise http_error(error) from error

    return app


async def _save_upload(upload: UploadFile, target: Path) -> None:
    with target.open("wb") as stream:
        while chunk := await upload.read(1024 * 1024):
            stream.write(chunk)


def _snapshot_node_by_path(nodes: dict, path: str):
    for node in nodes.values():
        if node.path == path:
            return node
    raise KeyError("node not found")


app = create_app()
