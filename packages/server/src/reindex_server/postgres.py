from __future__ import annotations

from importlib.resources import files

import psycopg


def initialize_database(database_url: str) -> None:
    """Install the ParadeDB BM25, pgvector, and relational serving schema."""
    schema = files("reindex_server").joinpath("schema.sql").read_text(encoding="utf-8")
    with (
        psycopg.connect(database_url, autocommit=True) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(schema)
