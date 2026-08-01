from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from uuid import UUID

import duckdb
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
from reindex_server.api_serialization import download, node_json, search_response
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
    async def create_collection(root_node: UploadFile = File(...)) -> dict:
        try:
            collection = app.state.service.create_collection(
                (await root_node.read()).decode("utf-8")
            )
            return collection.status_response()
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/raw/upload", response_model=RawUploadResponse)
    async def upload_raw(
        collection_id: UUID = Form(...),
        raw_path: str = Form(...),
        file: UploadFile = File(...),
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
            path = app.state.service.store.raw_file(
                request.collection_key, request.raw_path
            )
            if not path.is_file():
                raise KeyError("raw file not found")
            return download(path, request.disposition)
        except Exception as error:
            raise http_error(error) from error

    @app.post(
        "/v1/reindex/import",
        status_code=202,
        response_model=ImportAcceptedResponse,
    )
    async def import_reindex(
        background: BackgroundTasks,
        collection_id: UUID = Form(...),
        archive: UploadFile = File(...),
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
                include_body=True,
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/nodes/download")
    def download_node(request: DownloadNodeRequest):
        try:
            node = app.state.service.get_node(request.collection_key, request.node_key)
            if request.target == "source":
                if not node.source_uri or not node.source_uri.startswith("raw://"):
                    raise KeyError("Node has no raw source")
                path = app.state.service.store.raw_file(
                    request.collection_key, node.source_uri.removeprefix("raw://")
                )
            else:
                path = app.state.service.store.resource_file(node.resource_key or "")
            if not path.is_file():
                raise KeyError("Node download target not found")
            return download(path, request.disposition)
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
            if not request.sql.lstrip().casefold().startswith(
                ("select", "with")
            ) or ";" in request.sql.rstrip(";"):
                raise ValueError(
                    "only one read-only SELECT or CTE statement is allowed"
                )
            node = app.state.service.get_node(request.collection_key, request.node_key)
            if node.kind != "table" or not node.resource_key:
                raise ValueError("node is not a queryable table")
            connection = duckdb.connect(":memory:")
            connection.from_csv_auto(
                str(app.state.service.store.resource_file(node.resource_key))
            ).create_view("data")
            cursor = connection.execute(request.sql, request.params)
            columns = [column[0] for column in cursor.description]
            rows = [
                dict(zip(columns, row, strict=True)) for row in cursor.fetchmany(1000)
            ]
            return {"columns": columns, "rows": rows, "truncated": len(rows) == 1000}
        except Exception as error:
            raise http_error(error) from error

    return app


app = create_app()
