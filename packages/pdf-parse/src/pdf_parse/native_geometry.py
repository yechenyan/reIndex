from __future__ import annotations

import hashlib
import json
from importlib.metadata import version
from typing import Any

from .geometry import intersects
from .geometry_compact import RECORD_SCHEMAS, compact_page
from .io_utils import read_json
from .paths import ProjectPaths


def page_geometry(page: Any) -> dict[str, Any]:
    graphics = page.vector_graphics
    return {
        "page_num": page.page_num,
        "width": page.width,
        "height": page.height,
        "text_items": [_text_item(item, index) for index, item in enumerate(page.text_items)],
        "vector_graphics": {
            "lines": [_line(item, index) for index, item in enumerate(graphics.lines or [])],
            "shapes": [_shape(item, index) for index, item in enumerate(graphics.shapes or [])],
        }
        if graphics
        else None,
        "blocks": [_block(item, index) for index, item in enumerate(page.blocks or [])],
    }


def scoped_geometry(
    paths: ProjectPaths, regions: list[tuple[int, list[float]]]
) -> dict[str, Any]:
    pages = []
    for page_num, target in regions:
        raw = read_json(paths.helper / "native-geometry" / f"page-{page_num:04d}.json")
        if raw is None:
            raise ValueError(f"Missing native LiteParse geometry for page {page_num}")
        pages.append(compact_page(_scope_page(raw, target)))
    payload = {
        "liteparse_version": version("liteparse"),
        "coordinate_system": {
            "origin": "top-left",
            "x_direction": "right",
            "y_direction": "down",
            "unit": "pt",
        },
        "record_schemas": RECORD_SCHEMAS,
        "pages": pages,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {"revision": "sha256:" + hashlib.sha256(encoded.encode()).hexdigest(), **payload}


def _scope_page(page: dict[str, Any], target: list[float]) -> dict[str, Any]:
    graphics = page.get("vector_graphics") or {}
    return {
        "page_num": page["page_num"],
        "width": page["width"],
        "height": page["height"],
        "scope_bbox": target,
        "text_items": [
            item for item in page["text_items"] if intersects(_item_bbox(item), target)
        ],
        "vector_graphics": {
            "lines": [line for line in graphics.get("lines", []) if _line_intersects(line, target)],
            "shapes": [
                shape for shape in graphics.get("shapes", []) if intersects(shape["bbox"], target)
            ],
        },
        "blocks": [value for block in page["blocks"] if (value := _scope_block(block, target))],
    }


def _text_item(item: Any, index: int) -> dict[str, Any]:
    return {
        "index": index,
        "text": item.text,
        "x": item.x,
        "y": item.y,
        "width": item.width,
        "height": item.height,
        "rotation": item.rotation,
        "words": [
            {key: getattr(word, key) for key in ("text", "x", "y", "width", "height")}
            for word in (item.words or [])
        ],
    }


def _line(item: Any, index: int) -> dict[str, Any]:
    keys = ("x1", "y1", "x2", "y2", "stroke", "stroke_width", "stroke_color", "fill", "fill_color")
    return {"index": index, **{key: getattr(item, key) for key in keys}}


def _shape(item: Any, index: int) -> dict[str, Any]:
    keys = ("stroke", "stroke_color", "fill", "fill_color", "has_curve")
    return {"index": index, "bbox": list(item.bbox), **{key: getattr(item, key) for key in keys}}


def _block(item: Any, index: int) -> dict[str, Any]:
    return {
        "index": index,
        "kind": item.kind,
        "text": item.text,
        "bbox": _rect(item.bbox),
        "header": [_cell(cell) for cell in (item.header or [])],
        "rows": [[_cell(cell) for cell in row] for row in (item.rows or [])],
    }


def _cell(cell: Any) -> dict[str, Any]:
    return {"text": cell.text, "bbox": _rect(cell.bbox)}


def _rect(value: Any) -> dict[str, float] | None:
    if value is None:
        return None
    return {key: getattr(value, key) for key in ("x", "y", "width", "height")}


def _item_bbox(item: dict[str, Any]) -> list[float]:
    return [item[key] for key in ("x", "y", "width", "height")]


def _list_bbox(value: dict[str, float]) -> list[float]:
    return [value[key] for key in ("x", "y", "width", "height")]


def _scope_block(block: dict[str, Any], target: list[float]) -> dict[str, Any] | None:
    bbox = block.get("bbox")
    if not bbox or not intersects(_list_bbox(bbox), target):
        return None
    value = {key: block[key] for key in ("index", "kind", "text", "bbox")}
    value["header"] = [cell for cell in block["header"] if _cell_intersects(cell, target)]
    value["rows"] = [
        {"index": index, "cells": row}
        for index, row in enumerate(block["rows"])
        if any(_cell_intersects(cell, target) for cell in row)
    ]
    return value


def _cell_intersects(cell: dict[str, Any], target: list[float]) -> bool:
    return bool(cell.get("bbox") and intersects(_list_bbox(cell["bbox"]), target))


def _line_intersects(line: dict[str, Any], target: list[float]) -> bool:
    x, y, width, height = target
    return min(line["x1"], line["x2"]) <= x + width and max(line["x1"], line["x2"]) >= x and min(line["y1"], line["y2"]) <= y + height and max(line["y1"], line["y2"]) >= y
