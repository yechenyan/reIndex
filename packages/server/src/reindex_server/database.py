from __future__ import annotations

from types import TracebackType
from typing import Self

from pgvector.psycopg import register_vector
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


class Database:
    """Thread-safe PostgreSQL connection pool shared by catalog and search."""

    def __init__(
        self,
        database_url: str,
        *,
        min_size: int = 1,
        max_size: int = 10,
        timeout: float = 5.0,
    ) -> None:
        self.pool = ConnectionPool(
            conninfo=database_url,
            min_size=min_size,
            max_size=max_size,
            timeout=timeout,
            kwargs={"row_factory": dict_row, "prepare_threshold": None},
            configure=_configure,
            open=True,
        )
        self.pool.wait()

    def connection(self):
        return self.pool.connection()

    def close(self) -> None:
        self.pool.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def _configure(connection: Connection) -> None:
    register_vector(connection)
