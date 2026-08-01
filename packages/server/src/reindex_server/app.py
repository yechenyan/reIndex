from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import BackgroundTasks, FastAPI, File, Form, UploadFile

from reindex_server import __version__
from reindex_server.api_errors import http_error, install_api_error_handling
from reindex_server.api_models import (
    ERROR_RESPONSES,
    BrowseResponse,
    CollectionStatusResponse,
    HealthResponse,
    ImportAcceptedResponse,
    NodeDetail,
    RawUploadResponse,
    SearchApiResponse,
    TableQueryResponse,
)
from reindex_server.api_serialization import (
    node_json,
    resource_download,
    search_response,
)
from reindex_server.contracts import (
    BrowseRequest,
    CollectionRequest,
    DownloadNodeRequest,
    DownloadRawRequest,
    GrepRequest,
    NodeRequest,
    SearchRequest,
    TableQueryRequest,
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

    @app.get("/health", response_model=HealthResponse)
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.post("/v1/collections/create", response_model=CollectionStatusResponse)
    async def create_collection(root_node: Annotated[UploadFile, File()]) -> dict:
        try:
            collection = app.state.service.create_collection(await root_node.read())
            return collection.status_response()
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/raw/upload", response_model=RawUploadResponse)
    async def upload_raw(
        collection_id: Annotated[UUID, Form()],
        raw_path: Annotated[str, Form()],
        file: Annotated[UploadFile, File()],
    ) -> dict:
        try:
            return await app.state.service.upload_raw(
                str(collection_id), raw_path, file
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/raw/download")
    def download_raw(request: DownloadRawRequest):
        try:
            resource = app.state.service.get_raw(
                request.collection_key, request.raw_path
            )
            return resource_download(
                app.state.service.store, resource, request.disposition
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post(
        "/v1/reindex/import",
        status_code=202,
        response_model=ImportAcceptedResponse,
    )
    async def import_reindex(
        background: BackgroundTasks,
        collection_id: Annotated[UUID, Form()],
        archive: Annotated[UploadFile, File()],
    ) -> dict:
        try:
            collection_key = str(collection_id)
            app.state.service.queue_import(collection_key)
            background.add_task(
                app.state.service.import_bytes, collection_key, await archive.read()
            )
            return {"collection_id": collection_key, "status": "queued"}
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/collections/status", response_model=CollectionStatusResponse)
    def collection_status(request: CollectionRequest) -> dict:
        try:
            return app.state.service.catalog.get(
                request.collection_key
            ).status_response()
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/nodes/browse", response_model=BrowseResponse)
    def browse(request: BrowseRequest) -> dict:
        try:
            return {
                "nodes": [
                    node_json(node)
                    for node in app.state.service.browse(
                        request.collection_key,
                        str(request.parent_node_id) if request.parent_node_id else None,
                        request.recursive,
                    )
                ]
            }
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/nodes/get", response_model=NodeDetail)
    def get_node(request: NodeRequest) -> dict:
        try:
            return node_json(
                app.state.service.get_node(request.collection_key, request.node_key),
                include_detail=True,
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/nodes/download")
    def download_node(request: DownloadNodeRequest):
        try:
            ordinal = request.asset_ordinal or 0
            link = app.state.service.get_node_resource(
                request.collection_key, request.node_key, request.target, ordinal
            )
            return resource_download(
                app.state.service.store, link.resource, request.disposition
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/search", response_model=SearchApiResponse)
    def search(request: SearchRequest) -> dict:
        try:
            response = app.state.service.search(
                request.collection_key, request.options()
            )
            return search_response(
                app.state.service, request.collection_key, response, request
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/grep", response_model=SearchApiResponse)
    def grep(request: GrepRequest) -> dict:
        try:
            response = app.state.service.grep(
                request.collection_key,
                request.pattern,
                request.limit,
                request.regex,
                request.case_sensitive,
            )
            return search_response(app.state.service, request.collection_key, response)
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/tables/query", response_model=TableQueryResponse)
    def query_table(request: TableQueryRequest) -> dict:
        try:
            node = app.state.service.get_node(request.collection_key, request.node_key)
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


app = create_app()
