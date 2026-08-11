from __future__ import annotations

import asyncio
import io
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from reindex_server.api_docs import PULL_RESPONSES
from reindex_server.api_errors import http_error
from reindex_server.api_models import (
    BlobUploadResponse,
    FetchResponse,
    HistoryResponse,
    PushStartResponse,
    VersionedPushResponse,
)
from reindex_server.contracts import (
    CommitRequest,
    EmbeddingUploadRequest,
    FetchRequest,
    HistoryRequest,
    PushRequest,
    VersionedCollectionRequest,
)


def install_version_routes(app: FastAPI) -> None:
    @app.post("/v1/push", response_model=PushStartResponse, tags=["Versions"])
    def push(request: PushRequest) -> dict:
        try:
            return app.state.service.start_push(request)
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/push/blob", response_model=BlobUploadResponse, tags=["Versions"])
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

    @app.post(
        "/v1/push/commit", response_model=VersionedPushResponse, tags=["Versions"]
    )
    async def commit_push(request: CommitRequest) -> dict:
        try:
            return await asyncio.to_thread(
                app.state.service.commit_push, str(request.upload_id), request.embeddings
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/push/embeddings", tags=["Versions"])
    async def upload_embeddings(request: EmbeddingUploadRequest) -> dict:
        try:
            return await asyncio.to_thread(
                app.state.service.upload_embeddings,
                str(request.upload_id), request.embeddings,
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/fetch", response_model=FetchResponse, tags=["Versions"])
    def fetch(request: FetchRequest) -> dict:
        try:
            return app.state.service.fetch_version(
                request.collection_key, request.version_key
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post("/v1/history", response_model=HistoryResponse, tags=["Versions"])
    def history(request: HistoryRequest) -> dict:
        try:
            return app.state.service.history(
                request.collection_key, request.limit, request.cursor
            )
        except Exception as error:
            raise http_error(error) from error

    @app.post(
        "/v1/pull",
        response_class=StreamingResponse,
        responses=PULL_RESPONSES,
        tags=["Versions"],
    )
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


async def _save_upload(upload: UploadFile, target: Path) -> None:
    with target.open("wb") as stream:
        while chunk := await upload.read(1024 * 1024):
            stream.write(chunk)
