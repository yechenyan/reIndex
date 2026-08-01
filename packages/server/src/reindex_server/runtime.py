from __future__ import annotations

import os
from pathlib import Path

from reindex_server.catalog import Catalog
from reindex_server.config import (
    database_pool_settings_from_environment,
    database_url_from_environment,
)
from reindex_server.database import Database
from reindex_server.embeddings import provider_from_environment
from reindex_server.reranking import (
    provider_from_environment as reranker_from_environment,
)
from reindex_server.service import ReindexService
from reindex_server.storage import FileStore


def service_from_environment() -> tuple[ReindexService, Database | None]:
    database = None
    catalog = Catalog()
    search_backend = None
    if database_url := database_url_from_environment():
        from reindex_server.paradedb_search import ParadeDBSearch
        from reindex_server.postgres_catalog import PostgresCatalog

        database = Database(database_url, **database_pool_settings_from_environment())
        catalog = PostgresCatalog(database)
        search_backend = ParadeDBSearch(database)
    service = ReindexService(
        catalog,
        FileStore(Path(os.getenv("REINDEX_DATA_DIR", ".reindex-data"))),
        provider_from_environment(),
        search_backend,
        reranker_from_environment(),
    )
    return service, database
