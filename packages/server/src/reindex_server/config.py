from __future__ import annotations

import os

from psycopg.conninfo import make_conninfo


def database_url_from_environment() -> str | None:
    if database_url := os.getenv("DATABASE_URL"):
        return database_url
    host = os.getenv("PARADEDB_HOST")
    password = os.getenv("PARADEDB_PASSWORD")
    if not host or not password:
        return None
    return make_conninfo(
        host=host,
        port=os.getenv("PARADEDB_PORT", "5432"),
        dbname=os.getenv("PARADEDB_DATABASE", "paradedb"),
        user=os.getenv("PARADEDB_USER", "parade_admin"),
        password=password,
    )


def database_pool_settings_from_environment() -> dict:
    minimum = int(os.getenv("REINDEX_DB_POOL_MIN", "1"))
    maximum = int(os.getenv("REINDEX_DB_POOL_MAX", "10"))
    timeout = float(os.getenv("REINDEX_DB_POOL_TIMEOUT", "5"))
    if minimum < 0 or maximum < 1 or minimum > maximum or timeout <= 0:
        raise ValueError("invalid REINDEX_DB_POOL_MIN/MAX/TIMEOUT settings")
    return {"min_size": minimum, "max_size": maximum, "timeout": timeout}
