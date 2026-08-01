from __future__ import annotations

import csv
import re
from pathlib import Path

import duckdb


def query_csv(path: Path, sql: str, params: list, limit: int = 1000) -> dict:
    statement = sql.strip()
    if not re.match(r"^(select|with)\b", statement, flags=re.IGNORECASE):
        raise ValueError("only one read-only SELECT or CTE statement is allowed")
    if ";" in statement.rstrip(";"):
        raise ValueError("only one read-only SELECT or CTE statement is allowed")
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        try:
            columns = next(reader)
        except StopIteration as error:
            raise ValueError("table content is empty") from error
        rows = list(reader)
    connection = duckdb.connect(
        ":memory:",
        config={
            "enable_external_access": "false",
            "allow_unsigned_extensions": "false",
        },
    )
    try:
        connection.execute("SET memory_limit = '256MB'")
        connection.execute("SET threads = 1")
        definitions = ", ".join(f"{_identifier(name)} VARCHAR" for name in columns)
        connection.execute(f"CREATE TABLE data ({definitions})")
        if rows:
            placeholders = ", ".join("?" for _ in columns)
            connection.executemany(f"INSERT INTO data VALUES ({placeholders})", rows)
        cursor = connection.execute(statement, params)
        result_columns = [column[0] for column in cursor.description]
        values = cursor.fetchmany(limit + 1)
        return {
            "columns": result_columns,
            "rows": [
                dict(zip(result_columns, row, strict=True)) for row in values[:limit]
            ],
            "truncated": len(values) > limit,
        }
    finally:
        connection.close()


def _identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
