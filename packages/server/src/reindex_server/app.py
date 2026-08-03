from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from reindex_server import __version__
from reindex_server.api_docs import API_DESCRIPTION, OPENAPI_TAGS, install_api_docs
from reindex_server.api_errors import install_api_error_handling
from reindex_server.api_models import ERROR_RESPONSES
from reindex_server.api_routes import install_api_routes
from reindex_server.openapi_contract import install_openapi_contract
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
        description=API_DESCRIPTION,
        docs_url=None,
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
        responses=ERROR_RESPONSES,
    )
    app.state.service = service
    install_api_error_handling(app)
    install_api_docs(app)
    install_api_routes(app)
    install_openapi_contract(app)
    return app


app = create_app()
