from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _base(node_id: str, kind: str, title: str, description: str) -> list[str]:
    return [
        "---",
        'spec: "reindex/node@0.1"',
        f"id: {_quoted(node_id)}",
        f"kind: {_quoted(kind)}",
        f"title: {_quoted(title)}",
        f"description: {_quoted(description)}",
    ]


def _source(lines: list[str], source_name: str, source_sha256: str, pages: tuple[int, int] | None = None) -> None:
    lines.extend(["source:", f"  uri: {_quoted(f'raw://{source_name}')}", f'  sha256: "{source_sha256}"'])
    if pages:
        lines.extend(["  locator:", f"    pages: [{pages[0]}, {pages[1]}]"])


def _finish(path: Path, lines: list[str], body: str) -> None:
    path.write_text("\n".join(lines) + "\n---\n" + body.rstrip() + "\n", encoding="utf-8")


def write_group_node(
    path: Path,
    node_id: str,
    title: str,
    description: str,
    source_name: str | None = None,
    source_sha256: str | None = None,
) -> None:
    lines = _base(node_id, "group", title, description)
    if source_name and source_sha256:
        _source(lines, source_name, source_sha256)
    _finish(path, lines, f"# {title}\n\n{description}")


def write_text_node(
    path: Path,
    node_id: str,
    title: str,
    description: str,
    source_name: str,
    source_sha256: str,
    pages: tuple[int, int],
    body: str,
) -> None:
    lines = _base(node_id, "text", title, description)
    _source(lines, source_name, source_sha256, pages)
    _finish(path, lines, body)


def write_image_node(
    path: Path,
    node_id: str,
    title: str,
    description: str,
    source_name: str,
    source_sha256: str,
    pages: tuple[int, int],
    resource_path: Path,
    media_type: str,
    visual_description: str,
    ocr: str | None = None,
) -> None:
    lines = _base(node_id, "image", title, description)
    _source(lines, source_name, source_sha256, pages)
    lines.extend(
        [
            "resource:",
            f"  uri: {_quoted(f'./{resource_path.name}')}",
            f"  media_type: {_quoted(media_type)}",
            f'  sha256: "{_sha256(resource_path)}"',
        ]
    )
    body = f"## Description\n\n{visual_description}"
    if ocr:
        body += f"\n\n## OCR\n\n{ocr}"
    _finish(path, lines, body)


def write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(rows)


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _preview(headers: list[str], rows: list[list[str]], indices: list[int]) -> str:
    selected_headers = [_markdown_cell(headers[index]) for index in indices]
    lines = [
        "| " + " | ".join(selected_headers) + " |",
        "| " + " | ".join(["---"] * len(indices)) + " |",
    ]
    for row in rows[:5]:
        lines.append("| " + " | ".join(_markdown_cell(row[index]) for index in indices) + " |")
    return "\n".join(lines)


def write_table_node(
    path: Path,
    node_id: str,
    title: str,
    description: str,
    source_name: str,
    source_sha256: str,
    pages: tuple[int, int],
    resource_path: Path,
    columns: list[dict[str, str]],
    rows: list[list[str]],
    grain: str,
    preview_indices: list[int],
    warnings: list[str],
    primary_key: list[str] | None = None,
    visual_path: Path | None = None,
) -> None:
    lines = _base(node_id, "table", title, description)
    _source(lines, source_name, source_sha256, pages)
    lines.extend(
        [
            "resource:",
            f"  uri: {_quoted(f'./{resource_path.name}')}",
            '  media_type: "text/csv"',
            f'  sha256: "{_sha256(resource_path)}"',
            "table:",
            f"  row_count: {len(rows)}",
            f"  grain: {_quoted(grain)}",
            "  columns:",
        ]
    )
    for column in columns:
        lines.extend(
            [
                f"    - name: {_quoted(column['name'])}",
                f"      type: {_quoted(column['type'])}",
                f"      description: {_quoted(column['description'])}",
            ]
        )
        if "unit" in column:
            lines.append(f"      unit: {_quoted(column['unit'])}")
    if primary_key:
        values = ", ".join(_quoted(value) for value in primary_key)
        lines.append(f"  primary_key: [{values}]")
    lines.append("warnings:")
    lines.extend(f"  - {_quoted(warning)}" for warning in warnings)
    headers = [column["name"] for column in columns]
    body = (
        f"## Dataset\n\n{description} Die vollständigen {len(rows)} Zeilen liegen in "
        f"`{resource_path.name}`.\n\n## Preview\n\n{_preview(headers, rows, preview_indices)}"
    )
    if visual_path:
        body += (
            "\n\n## Visual reference\n\n"
            f"[Open {visual_path.name}](./{visual_path.name})\n\n"
            f"SHA-256: `{_sha256(visual_path)}`"
        )
    _finish(path, lines, body)
