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
    HealthResponse,
    PushResponse,
    SearchApiResponse,
    TableQueryResponse,
)
from reindex_server.api_serialization import resource_download, search_response
from reindex_server.contracts import (
    CollectionRequest,
    GetRequest,
    GrepRequest,
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

    def collection_id(name: str) -> str:
        return app.state.service.resolve_collection(name).id

    @app.get("/health", response_model=HealthResponse)
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.post("/v1/push", response_model=PushResponse)
    async def push(
        name: Annotated[str, Form()],
        package: Annotated[UploadFile, File()],
        sources: Annotated[UploadFile, File()],
    ) -> dict:
        try:
            with tempfile.TemporaryDirectory(prefix="reindex-api-push-") as directory:
                package_path = Path(directory) / "package.zip"
                sources_path = Path(directory) / "sources.zip"
                await _save_upload(package, package_path)
                await _save_upload(sources, sources_path)
                return app.state.service.push(name, package_path, sources_path)
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/pull")
    def pull(request: CollectionRequest):
        try:
            content, collection = app.state.service.pull(request.collection_key)
            headers = {
                "Content-Disposition": (
                    f'attachment; filename="{collection.name}-nodes.zip"'
                ),
                "Content-Length": str(len(content)),
                "X-ReIndex-Package-Hash": collection.package_hash or "",
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
            if request.raw_uri is not None:
                resource = app.state.service.get_raw(
                    resolved_id, request.raw_uri.removeprefix("raw://")
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


app = create_app()
