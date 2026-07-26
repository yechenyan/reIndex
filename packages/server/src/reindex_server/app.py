from __future__ import annotations

import os
from pathlib import Path

import duckdb
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from reindex_server import __version__
from reindex_server.catalog import Catalog
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
from reindex_server.embeddings import provider_from_environment
from reindex_server.service import ReindexService
from reindex_server.storage import FileStore


def create_app(service: ReindexService | None = None) -> FastAPI:
    app = FastAPI(title="ReIndex API", version=__version__)
    app.state.service = service or ReindexService(
        Catalog(), FileStore(Path(os.getenv("REINDEX_DATA_DIR", ".reindex-data"))), provider_from_environment()
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.post("/v1/collections/create")
    async def create_collection(root_node: UploadFile = File(...)) -> dict:
        try:
            collection = app.state.service.create_collection((await root_node.read()).decode("utf-8"))
            return collection.status_response()
        except Exception as error:
            raise _http_error(error) from error

    @app.post("/v1/raw/upload")
    async def upload_raw(collection_id: str = Form(...), raw_path: str = Form(...), file: UploadFile = File(...)) -> dict:
        try:
            return await app.state.service.upload_raw(collection_id, raw_path, file)
        except Exception as error:
            raise _http_error(error) from error

    @app.post("/v1/raw/download")
    def download_raw(request: DownloadRawRequest):
        try:
            path = app.state.service.store.raw_file(request.collection_id, request.raw_path)
            if not path.is_file():
                raise KeyError("raw file not found")
            return _download(path, request.disposition)
        except Exception as error:
            raise _http_error(error) from error

    @app.post("/v1/reindex/import", status_code=202)
    async def import_reindex(background: BackgroundTasks, collection_id: str = Form(...), archive: UploadFile = File(...)) -> dict:
        try:
            app.state.service.queue_import(collection_id)
            background.add_task(app.state.service.import_bytes, collection_id, await archive.read())
            return {"collection_id": collection_id, "status": "queued"}
        except Exception as error:
            raise _http_error(error) from error

    @app.post("/v1/collections/status")
    def collection_status(request: CollectionRequest) -> dict:
        try:
            return app.state.service.catalog.get(request.collection_id).status_response()
        except Exception as error:
            raise _http_error(error) from error

    @app.post("/v1/nodes/browse")
    def browse(request: BrowseRequest) -> dict:
        try:
            return {"nodes": [_node_json(node) for node in app.state.service.browse(request.collection_id, request.parent_node_id)]}
        except Exception as error:
            raise _http_error(error) from error

    @app.post("/v1/nodes/get")
    def get_node(request: NodeRequest) -> dict:
        try:
            return _node_json(app.state.service.get_node(request.collection_id, request.node_id), include_body=True)
        except Exception as error:
            raise _http_error(error) from error

    @app.post("/v1/nodes/download")
    def download_node(request: DownloadNodeRequest):
        try:
            node = app.state.service.get_node(request.collection_id, request.node_id)
            if request.target == "source":
                if not node.source_uri or not node.source_uri.startswith("raw://"):
                    raise KeyError("Node has no raw source")
                path = app.state.service.store.raw_file(request.collection_id, node.source_uri.removeprefix("raw://"))
            else:
                path = app.state.service.store.resource_file(node.resource_key or "")
            if not path.is_file():
                raise KeyError("Node download target not found")
            return _download(path, request.disposition)
        except Exception as error:
            raise _http_error(error) from error

    @app.post("/v1/search")
    def search(request: SearchRequest) -> dict:
        try:
            mode, results = app.state.service.search(request.collection_id, request.query, request.mode, request.limit)
            return {"executed_mode": mode, "results": [_result(app.state.service, request.collection_id, unit, score) for unit, score in results]}
        except Exception as error:
            raise _http_error(error) from error

    @app.post("/v1/grep")
    def grep(request: GrepRequest) -> dict:
        return search(request)

    @app.post("/v1/tables/query")
    def query_table(request: TableQueryRequest) -> dict:
        try:
            if not request.sql.lstrip().casefold().startswith(("select", "with")) or ";" in request.sql.rstrip(";"):
                raise ValueError("only one read-only SELECT or CTE statement is allowed")
            node = app.state.service.get_node(request.collection_id, request.node_id)
            if node.kind != "table" or not node.resource_key:
                raise ValueError("node is not a queryable table")
            connection = duckdb.connect(":memory:")
            connection.from_csv_auto(str(app.state.service.store.resource_file(node.resource_key))).create_view("data")
            cursor = connection.execute(request.sql, request.params)
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchmany(1000)]
            return {"columns": columns, "rows": rows, "truncated": len(rows) == 1000}
        except Exception as error:
            raise _http_error(error) from error

    return app


def _node_json(node, include_body: bool = False) -> dict:
    value = {"id": node.id, "path": node.path, "parent_id": node.parent_id, "kind": node.kind, "title": node.title, "description": node.description, "locator": node.locator}
    if include_body:
        value.update({"body": node.body, "source_uri": node.source_uri, "resource_uri": node.resource_uri, "table": node.table})
    return value


def _result(service, collection_id: str, unit, score: float) -> dict:
    node = service.get_node(collection_id, unit.node_id)
    return {"score": score, "evidence": {**_node_json(node), "excerpt": unit.excerpt, "source_sha256": node.source_sha256, "row": unit.row}}


def _download(path: Path, disposition: str) -> FileResponse:
    return FileResponse(path, filename=path.name, content_disposition_type=disposition)


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(404, str(error))
    if isinstance(error, RuntimeError):
        return HTTPException(409, str(error))
    return HTTPException(400, str(error))


app = create_app()
