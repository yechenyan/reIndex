from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from pdf_table_codegen.models import ExtractionResult


def sample_indices(row_count: int) -> list[int]:
    if row_count < 0:
        raise ValueError("row_count cannot be negative")
    if row_count <= 3:
        return list(range(row_count))
    return [0, 1, row_count - 2, row_count - 1]


def _normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value)).replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def load_reference(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("spec") != "pdf-table-codegen/reference@1.0":
        raise ValueError("unsupported visual reference spec")
    return value


def verify_reference(result: ExtractionResult, reference: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, expected: Any, actual: Any) -> None:
        checks.append({"name": name, "ok": ok, "expected": expected, "actual": actual})

    check(
        "source_sha256",
        result.source_sha256 == reference.get("source_sha256"),
        reference.get("source_sha256"),
        result.source_sha256,
    )
    actual_tables = {table.id: table for table in result.tables}
    expected_tables = reference.get("tables") or []
    check("table_count", len(actual_tables) == len(expected_tables), len(expected_tables), len(actual_tables))
    for expected in expected_tables:
        table_id = expected["id"]
        table = actual_tables.get(table_id)
        check(f"{table_id}.present", table is not None, True, table is not None)
        if table is None:
            continue
        check(f"{table_id}.columns", len(table.headers) == expected["column_count"], expected["column_count"], len(table.headers))
        check(f"{table_id}.rows", len(table.rows) == expected["row_count"], expected["row_count"], len(table.rows))
        expected_header = [_normalized(value) for value in expected["header"]]
        actual_header = [_normalized(value) for value in table.headers]
        check(f"{table_id}.header", actual_header == expected_header, expected_header, actual_header)
        for sample in expected.get("samples", []):
            index = int(sample["row_index"])
            actual = table.rows[index] if 0 <= index < len(table.rows) else None
            expected_row = [_normalized(value) for value in sample["values"]]
            actual_row = None if actual is None else [_normalized(value) for value in actual]
            check(f"{table_id}.row[{index}]", actual_row == expected_row, expected_row, actual_row)
    return {
        "spec": "pdf-table-codegen/verification@1.0",
        "ok": all(item["ok"] for item in checks) and result.qa.ok,
        "extractor_qa": result.qa.to_dict(),
        "checks": checks,
    }
