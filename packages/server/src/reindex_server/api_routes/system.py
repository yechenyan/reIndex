from __future__ import annotations

from fastapi import FastAPI

from reindex_server import __version__
from reindex_server.api_models import HealthResponse


def install_system_routes(app: FastAPI) -> None:
    @app.get("/health", response_model=HealthResponse, tags=["System"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}
