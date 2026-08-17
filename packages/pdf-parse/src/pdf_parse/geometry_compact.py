from __future__ import annotations

from typing import Any


RECORD_SCHEMAS = {
    "text_item": ["index", "text", "x", "y", "width", "height", "rotation", "words"],
    "word": ["text", "x", "y", "width", "height"],
    "line": [
        "index", "x1", "y1", "x2", "y2", "stroke", "stroke_width",
        "stroke_color", "fill", "fill_color",
    ],
    "shape": [
        "index", "bbox", "stroke", "stroke_color", "fill", "fill_color", "has_curve",
    ],
    "block": ["index", "kind", "text", "bbox", "header", "rows"],
    "cell": ["text", "bbox"],
    "row": ["index", "cells"],
}


def compact_page(page: dict[str, Any]) -> dict[str, Any]:
    graphics = page["vector_graphics"]
    return {
        "page_num": page["page_num"],
        "width": page["width"],
        "height": page["height"],
        "scope_bbox": page["scope_bbox"],
        "text_items": [_text_item(item) for item in page["text_items"]],
        "vector_graphics": {
            "lines": [_record("line", line) for line in graphics["lines"]],
            "shapes": [_record("shape", shape) for shape in graphics["shapes"]],
        },
        "blocks": [_block(block) for block in page["blocks"]],
    }


def _text_item(item: dict[str, Any]) -> list[Any]:
    values = _record("text_item", item)
    values[-1] = [_record("word", word) for word in item["words"]]
    return values


def _block(block: dict[str, Any]) -> list[Any]:
    return [
        block["index"],
        block["kind"],
        block["text"],
        _bbox(block["bbox"]),
        [_cell(cell) for cell in block["header"]],
        [[row["index"], [_cell(cell) for cell in row["cells"]]] for row in block["rows"]],
    ]


def _cell(cell: dict[str, Any]) -> list[Any]:
    return [cell["text"], _bbox(cell["bbox"])]


def _bbox(value: dict[str, float] | None) -> list[float] | None:
    if not value:
        return None
    return [value[key] for key in ("x", "y", "width", "height")]


def _record(name: str, value: dict[str, Any]) -> list[Any]:
    return [value.get(key) for key in RECORD_SCHEMAS[name]]
