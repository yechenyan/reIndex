from __future__ import annotations

import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from reindex_cli.errors import ReIndexError


def read_csv_rows(path: Path, label: str) -> tuple[list[str], list[list[str]]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
    except (OSError, UnicodeError, csv.Error) as error:
        raise ReIndexError(f"Could not read CSV: {label}: {error}") from error
    if (
        not rows
        or not rows[0]
        or any(not value for value in rows[0])
        or len(set(rows[0])) != len(rows[0])
    ):
        raise ReIndexError(f"CSV header must be non-empty and unique: {label}")
    headers, data = rows[0], rows[1:]
    if any(len(row) != len(headers) for row in data):
        raise ReIndexError(f"CSV row width mismatch: {label}")
    return headers, data


def csv_profile(path: Path, label: str) -> dict:
    headers, data = read_csv_rows(path, label)
    return {
        "row_count": len(data),
        "columns": [
            {
                "name": name,
                "type": infer_type([row[index] for row in data]),
            }
            for index, name in enumerate(headers)
        ],
    }


def pdf_profile(path: Path, label: str) -> dict:
    try:
        from pypdfium2 import PdfDocument

        document = PdfDocument(path)
        try:
            page_count = len(document)
            if page_count < 1:
                raise ReIndexError(f"Invalid PDF: {label}")
            return {"page_count": page_count}
        finally:
            document.close()
    except ReIndexError:
        raise
    except Exception as error:
        raise ReIndexError(f"Could not inspect PDF: {label}: {error}") from error


def infer_type(values: list[str]) -> str:
    nonempty = [value.strip() for value in values if value.strip()]
    if not nonempty:
        return "string"
    if all(
        re.fullmatch(r"[-+]?\d+", value)
        and not (len(value.lstrip("+-")) > 1 and value.lstrip("+-").startswith("0"))
        for value in nonempty
    ):
        return "integer"
    try:
        for value in nonempty:
            Decimal(value.replace(",", "."))
        return "decimal"
    except InvalidOperation:
        return "string"
