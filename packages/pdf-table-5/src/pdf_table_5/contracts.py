from __future__ import annotations

from typing import Iterable


MERGE_VALUES = {"yes", "possible", "no"}
# Agent-produced page-edge coordinates are commonly rounded to whole points,
# while PDF page dimensions retain fractional points (for example 841.92pt).
BOUNDARY_TOLERANCE_PT = 1.0


def validate_find_tables(value: dict, pages: list[dict]) -> dict:
    tables = require_list(value, "tables")
    page_map = {item["page"]: item for item in pages}
    seen: set[str] = set()
    previous = None
    previous_page = None
    for index, table in enumerate(tables, start=1):
        require_dict(table, f"tables[{index - 1}]")
        identifier = str(table.get("findTableId", f"find_{index:04d}"))
        if identifier in seen:
            raise ValueError(f"Duplicate findTableId: {identifier}")
        seen.add(identifier)
        table["findTableId"] = identifier
        table.setdefault("preFindTableId", previous)
        page = require_int(table, "page")
        if page not in page_map:
            raise ValueError(f"Invalid page {page}")
        table["bbox"] = valid_bbox(table.get("bbox"), page_map[page])
        merge = table.get("mergeWithPrevious", "no")
        if merge not in MERGE_VALUES or previous is None and merge != "no":
            raise ValueError(f"Invalid mergeWithPrevious for {identifier}: {merge}")
        if merge != "no" and previous_page is not None and page > previous_page + 1:
            raise ValueError(f"Cannot merge nonconsecutive pages {previous_page} and {page}")
        table["mergeWithPrevious"] = merge
        table.setdefault("recommendedDpi", 216)
        previous = identifier
        previous_page = page
    return value


def validate_merge_tables(value: dict, find_ids: set[str]) -> dict:
    groups = require_list(value, "tables")
    used: set[str] = set()
    for group in groups:
        members = require_list(group, "tables")
        if not members:
            raise ValueError("Merge group cannot be empty")
        for member in members:
            identifier = str(member.get("findTableId", ""))
            if identifier not in find_ids or identifier in used:
                raise ValueError(f"Invalid or repeated findTableId in merge output: {identifier}")
            used.add(identifier)
    if used != find_ids:
        raise ValueError(f"Merge output omitted IDs: {sorted(find_ids - used)}")
    return value


def require_list(value: dict, key: str) -> list:
    if not isinstance(value, dict) or not isinstance(value.get(key), list):
        raise ValueError(f"Expected object with array {key}")
    return value[key]


def require_dict(value, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"Expected object at {label}")
    return value


def require_int(value: dict, key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int):
        raise ValueError(f"Expected integer {key}")
    return item


def valid_bbox(value, page: dict) -> list[float]:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("bbox must be [x0, y0, x1, y1]")
    x0, y0, x1, y1 = map(float, value)
    width, height = float(page["width"]), float(page["height"])
    if not (
        -BOUNDARY_TOLERANCE_PT < x0 < x1 < width + BOUNDARY_TOLERANCE_PT
        and -BOUNDARY_TOLERANCE_PT < y0 < y1 < height + BOUNDARY_TOLERANCE_PT
    ):
        raise ValueError(f"bbox outside page: {value}")
    return [round(item, 3) for item in (max(0.0, x0), max(0.0, y0), min(width, x1), min(height, y1))]


def unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))
