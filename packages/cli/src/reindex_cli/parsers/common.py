from __future__ import annotations

from reindex_cli.pipeline.models import DraftNode


def description_for(title: str, kind: str) -> str:
    labels = {
        "text": "Readable text",
        "table": "Structured tabular data",
        "image": "Extracted image",
        "file": "Source file",
        "group": "Document group",
    }
    return f"{labels[kind]} for {title}."


def initial_body(node: DraftNode) -> str:
    if node.kind == "table" and node.table:
        return _table_body(node)
    if node.kind == "group":
        return f"## Overview\n\n{node.description}\n"
    lines = ["## Overview", "", node.description]
    lines.extend(_position(node))
    if node.kind == "image":
        lines.extend(_image_context(node))
    return "\n".join(lines) + "\n"


def _table_body(node: DraftNode) -> str:
    lines = ["## Overview", "", node.description]
    lines.extend(_position(node))
    nearby = node.context.get("nearby_text")
    if nearby:
        lines.extend(["", "## Nearby source text", "", nearby])
    lines.extend(["", "## Data profile", ""])
    lines.extend(_profile_table(node.table.get("profile", [])))
    lines.extend(["", "## Preview", ""])
    preview = node.table.get("preview", [])
    if preview:
        columns = list(preview[0])
        lines.extend(
            [
                "| " + " | ".join(columns) + " |",
                "| " + " | ".join("---" for _ in columns) + " |",
            ]
        )
        for row in preview:
            lines.append(
                "| "
                + " | ".join(str(row[name]).replace("|", "\\|") for name in columns)
                + " |"
            )
    return "\n".join(lines) + "\n"


def _position(node: DraftNode) -> list[str]:
    path = node.context.get("section_path")
    lines: list[str] = []
    if path or node.pages:
        lines.extend(["", "## Document position", ""])
    if path:
        lines.append("- Section: " + " > ".join(f"`{value}`" for value in path))
    if node.pages:
        page = (
            str(node.pages[0])
            if node.pages[0] == node.pages[1]
            else f"{node.pages[0]}–{node.pages[1]}"
        )
        lines.append(f"- Pages: {page}")
    return lines


def _profile_table(profile: list[dict]) -> list[str]:
    if not profile:
        return ["No field statistics were available."]
    lines = [
        "| Field | Type | Non-empty | Missing | Missing rate | Unique | Min | Max |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for value in profile:
        cells = [
            value["name"],
            value["type"],
            value["non_empty_count"],
            value["missing_count"],
            f"{value['missing_rate']:.1%}",
            value["unique_count"],
            value.get("min", ""),
            value.get("max", ""),
        ]
        lines.append("| " + " | ".join(_cell(cell) for cell in cells) + " |")
    return lines


def _image_context(node: DraftNode) -> list[str]:
    width = node.context.get("width")
    height = node.context.get("height")
    nearby = node.context.get("nearby_text")
    lines: list[str] = []
    if width and height:
        lines.extend(
            ["", "## Image information", "", f"- Dimensions: {width} × {height}"]
        )
    if nearby:
        lines.extend(["", "## Nearby source text", "", nearby])
    return lines


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
