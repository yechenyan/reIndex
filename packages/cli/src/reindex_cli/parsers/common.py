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
    return (
        f"## Overview\n\n{node.description}\n\nReview and enrich this card as needed.\n"
    )


def _table_body(node: DraftNode) -> str:
    lines = ["## Overview", "", node.description, "", "## Preview", ""]
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
