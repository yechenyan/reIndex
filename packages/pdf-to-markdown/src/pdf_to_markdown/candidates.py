from __future__ import annotations

import re

from .markdown_tables import complex_page_span, find_tables, page_offsets


INLINE_MARKUP = re.compile(r"[*_`]+")


def discover(liteparse: dict) -> list[dict]:
    pages = liteparse["pages"]
    offsets = page_offsets(liteparse["markdown"], pages)
    candidates: list[dict] = []
    by_number = {page["page"]: page for page in pages}
    for page in pages:
        number = page["page"]
        if direct_page_signal(page):
            candidates.append(page_candidate(page, offsets[number], "dense page table evidence"))
            continue
        blocks = find_tables(page["markdown"])
        for block in blocks:
            bbox = locate_bbox(page, block["matrix"])
            reasons = direct_table_reasons(block["matrix"], bbox)
            candidates.append(
                base_candidate(
                    pages=[number],
                    bboxes=[bbox or [0.0, 0.0, page["width"], page["height"]]],
                    spans=[[offsets[number] + block["start"], offsets[number] + block["end"]]],
                    matrix=block["matrix"],
                    route="specialist" if reasons else "sample",
                    reasons=reasons,
                    source="markdown-table",
                )
            )
        if table_signal(page) and not blocks:
            candidates.append(page_candidate(page, offsets[number], "table signal without valid Markdown"))
    candidates.sort(key=lambda item: (item["pages"][0], item["spans"][0][0] if item["spans"] else 0))
    for index, candidate in enumerate(candidates, start=1):
        candidate["tableId"] = f"table_{index:04d}"
        candidate["pageBounds"] = [
            [offsets[number], offsets[number] + len(by_number[number]["markdown"])]
            for number in candidate["pages"]
        ]
    return candidates


def page_candidate(page: dict, offset: int, reason: str) -> dict:
    span = complex_page_span(page["markdown"], continues=False) or (0, len(page["markdown"]))
    return base_candidate(
        pages=[page["page"]],
        bboxes=[[0.0, 0.0, page["width"], page["height"]]],
        spans=[[offset + span[0], offset + span[1]]],
        matrix=[],
        route="specialist",
        reasons=[reason],
        source="page-table-signal",
    )


def base_candidate(*, pages, bboxes, spans, matrix, route, reasons, source) -> dict:
    return {
        "tableId": "",
        "pages": pages,
        "bboxes": bboxes,
        "spans": spans,
        "matrix": matrix,
        "route": route,
        "routeReasons": reasons,
        "source": source,
        "status": "pending",
    }


def direct_page_signal(page: dict) -> bool:
    layout = ((page.get("complexity") or {}).get("layout") or {})
    return int(layout.get("text_table_run_count") or 0) >= 3 or vector_line_count(page) >= 80


def table_signal(page: dict) -> bool:
    layout = ((page.get("complexity") or {}).get("layout") or {})
    return bool(layout.get("ruled_table_count") or layout.get("text_table_run_count") or vector_line_count(page) >= 80)


def vector_line_count(page: dict) -> int:
    return len(page.get("vectorLines") or [])


def direct_table_reasons(matrix: list[list[str]], bbox) -> list[str]:
    reasons = []
    if bbox is None:
        reasons.append("table cells could not be localized reliably on the PDF page")
    if matrix and not any(normalize(cell) for cell in matrix[0]):
        reasons.append("Markdown table has an empty header row")
    if matrix and len(matrix[0]) > 8:
        reasons.append("table is wider than the simple-table gate")
    if any("|" in cell or "**" in cell for row in matrix for cell in row):
        reasons.append("Markdown cells contain structural artifacts")
    return reasons


def locate_bbox(page: dict, matrix: list[list[str]]) -> list[float] | None:
    values = {normalize(cell) for row in matrix for cell in row if normalize(cell)}
    matches = []
    for item in page.get("textItems", []):
        text = normalize(item.get("text", ""))
        if text in values:
            matches.append(item)
    if len(matches) < 3:
        return None
    clusters = cluster_by_y(matches)
    selected = max(clusters, key=len)
    matched_values = {normalize(item["text"]) for item in selected}
    if len(matched_values) < max(2, round(len(values) * 0.25)):
        return None
    x0 = min(item["x"] for item in selected)
    y0 = min(item["y"] for item in selected)
    x1 = max(item["x"] + item["width"] for item in selected)
    y1 = max(item["y"] + item["height"] for item in selected)
    margin = 14.0
    return [max(0.0, x0 - margin), max(0.0, y0 - margin), min(page["width"], x1 + margin), min(page["height"], y1 + margin)]


def cluster_by_y(items: list[dict]) -> list[list[dict]]:
    ordered = sorted(items, key=lambda item: (item["y"], item["x"]))
    clusters: list[list[dict]] = []
    for item in ordered:
        if not clusters or item["y"] - clusters[-1][-1]["y"] > 50:
            clusters.append([])
        clusters[-1].append(item)
    return clusters


def normalize(value: str) -> str:
    text = INLINE_MARKUP.sub("", str(value))
    return re.sub(r"\s+", " ", text).strip().casefold()

