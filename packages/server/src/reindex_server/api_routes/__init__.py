from __future__ import annotations

from fastapi import FastAPI

from reindex_server.api_routes.collections import install_collection_routes
from reindex_server.api_routes.resources import install_resource_routes
from reindex_server.api_routes.search import install_search_routes
from reindex_server.api_routes.system import install_system_routes
from reindex_server.api_routes.versions import install_version_routes


def install_api_routes(app: FastAPI) -> None:
    install_system_routes(app)
    install_collection_routes(app)
    install_version_routes(app)
    install_resource_routes(app)
    install_search_routes(app)
