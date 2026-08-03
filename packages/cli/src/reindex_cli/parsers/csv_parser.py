from __future__ import annotations

import csv
import io
import re

from reindex_cli.errors import ReIndexError
from reindex_cli.parsers.common import initial_body
from reindex_cli.parsers.profiles import read_csv_rows
from reindex_cli.parsers.table_profile import build_table_profile, table_columns
from reindex_cli.pipeline.models import DraftNode, SourceItem


def parse_csv(item: SourceItem) -> list[DraftNode]:
    headers, data = read_csv_rows(item.path, item.relative)
    _validate_quality(item, headers, data)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows([headers, *data])
    title = item.config.title or _title(item.path.stem)
    profile = build_table_profile(headers, data)
    columns = table_columns(profile)
    table = {
        "row_count": len(data),
        "grain": "One row from the source table.",
        "columns": columns,
        "profile": profile,
        "preview": [dict(zip(headers, row, strict=True)) for row in data[:5]],
    }
    if primary := (item.config.quality or {}).get("primary_key"):
        table["primary_key"] = primary
    source = item.config.part_of or item.config.derived_from or item.relative
    node = DraftNode(
        logical_key=item.relative,
        item_path=item.relative,
        kind="table",
        title=title,
        description=item.config.description
        or f"Table with {len(data)} rows and {len(headers)} columns: "
        + ", ".join(headers[:6])
        + ("." if len(headers) <= 6 else ", and additional fields."),
        source_path=source,
        pages=item.config.pages,
        content=output.getvalue().encode(),
        extension="csv",
        media_type="text/csv",
        table=table,
        order_hint=((item.config.pages[0] if item.config.pages else 0), item.relative),
    )
    node.body = initial_body(node)
    return [node]


def _validate_quality(
    item: SourceItem, headers: list[str], data: list[list[str]]
) -> None:
    quality = item.config.quality or {}
    if "expected_rows" in quality and quality["expected_rows"] != len(data):
        raise ReIndexError(f"expected_rows failed for {item.relative}: {len(data)}")
    if "expected_columns" in quality and quality["expected_columns"] != headers:
        raise ReIndexError(f"expected_columns failed for {item.relative}")
    if primary := quality.get("primary_key"):
        if any(name not in headers for name in primary):
            raise ReIndexError(f"primary_key column missing: {item.relative}")
        indices = [headers.index(name) for name in primary]
        keys = [tuple(row[index] for index in indices) for row in data]
        if any(not all(key) for key in keys) or len(keys) != len(set(keys)):
            raise ReIndexError(
                f"primary_key must be non-empty and unique: {item.relative}"
            )


def _title(stem: str) -> str:
    value = re.sub(r"^\d{5}--", "", stem)
    return value.replace("_", " ").replace("-", " ").strip().title()
