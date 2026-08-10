from __future__ import annotations

from importlib.resources import files

import psycopg


def initialize_database(database_url: str) -> None:
    """Install the serving schema once, without resetting an existing database."""
    schema = files("reindex_server").joinpath("schema.sql").read_text(encoding="utf-8")
    with (
        psycopg.connect(database_url, autocommit=True) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute("SELECT pg_advisory_lock(hashtext('reindex-schema-init'))")
        try:
            cursor.execute("SELECT to_regclass('public.collections')")
            collection_table = cursor.fetchone()[0]
            if collection_table is None:
                cursor.execute(schema)
        finally:
            cursor.execute("SELECT pg_advisory_unlock(hashtext('reindex-schema-init'))")
