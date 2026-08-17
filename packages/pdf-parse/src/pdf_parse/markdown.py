from __future__ import annotations

from html import escape
from typing import Any


def row_matrix_markdown(rows: list[list[Any]]) -> str:
    rendered = [
        "<tr>"
        + "".join(f"<td>{escape(str(value or '')).replace(chr(10), '<br>')}</td>" for value in row)
        + "</tr>"
        for row in rows
    ]
    return "<table><tbody>" + "".join(rendered) + "</tbody></table>"


def table_markdown(header: list[Any], rows: list[list[Any]]) -> str:
    grid = [header, *rows] if header else rows
    if not grid:
        return ""
    width = max(len(row) for row in grid)
    normalized = [[str(cell or "") for cell in row] + [""] * (width - len(row)) for row in grid]
    if width <= 10 and all("\n" not in cell and "|" not in cell for row in normalized for cell in row):
        head = normalized[0]
        data = normalized[1:]
        lines = ["| " + " | ".join(head) + " |", "| " + " | ".join(["---"] * width) + " |"]
        lines.extend("| " + " | ".join(row) + " |" for row in data)
        return "\n".join(lines)
    body = []
    if header:
        body.append("<thead><tr>" + "".join(f"<th>{escape(str(v or ''))}</th>" for v in header) + "</tr></thead>")
        source_rows = rows
    else:
        source_rows = normalized
    rendered = ["<tr>" + "".join(f"<td>{escape(str(v or '')).replace(chr(10), '<br>')}</td>" for v in row) + "</tr>" for row in source_rows]
    body.append("<tbody>" + "".join(rendered) + "</tbody>")
    return "<table>" + "".join(body) + "</table>"


def liteparse_block_markdown(block: Any) -> str:
    if block.kind == "heading":
        return f"{'#' * int(block.level or 2)} {block.text or ''}".strip()
    if block.kind == "paragraph":
        return block.text or ""
    if block.kind == "list_item":
        marker = "1." if block.ordered else "-"
        return f"{marker} {block.text or ''}".strip()
    if block.kind in {"code", "grid_fallback"}:
        return "```\n" + "\n".join(block.lines or []) + "\n```"
    if block.kind == "table":
        header = [cell.text for cell in (block.header or [])]
        rows = [[cell.text for cell in row] for row in (block.rows or [])]
        return table_markdown(header, rows)
    if block.kind == "rule":
        return "---"
    return ""
