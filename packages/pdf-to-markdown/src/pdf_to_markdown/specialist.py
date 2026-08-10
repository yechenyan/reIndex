from __future__ import annotations

import csv
import shutil
from pathlib import Path

from pdf_table_5 import execute, initialize

from .io import read_json
from .specialist_pages import pages_for, partition_replacements


def run_specialist(
    pdf: Path,
    project: Path,
    candidates: list[dict],
    *,
    model: str,
    reasoning_effort: str,
) -> dict:
    targets = [candidate for candidate in candidates if candidate["route"] == "specialist"]
    if not targets:
        return {"pages": [], "report": None, "replacements": [], "unmatched": [], "failed": []}
    pages = sorted({page for candidate in targets for page in candidate["pages"]})
    initialize_for_pages(pdf, project, pages)
    try:
        report = execute(project, model=model, reasoning_effort=reasoning_effort)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        for candidate in targets:
            candidate["status"] = "specialist_failed"
            candidate["routeReasons"].append(error)
        return {
            "pages": pages,
            "report": {"accepted": False, "workflowError": error},
            "replacements": [],
            "unmatched": [],
            "failed": ["workflow"],
            "error": error,
        }
    final = read_json(project / "output" / "finalTable.json", {"tables": []})
    for candidate in targets:
        candidate["status"] = "specialist_no_table"
    items = final.get("tables", [])
    valid = [item for item in items if item.get("accepted") and item.get("outputPath")]
    invalid = [item for item in items if item not in valid]
    eligible, blocked, blocked_pages = partition_replacements(items)
    replacements, used = plan_replacements(candidates, eligible)
    by_id = {candidate["tableId"]: candidate for candidate in candidates}
    for replacement in replacements:
        details = replacement["specialist"]
        for table_id in replacement["affectedTableIds"]:
            candidate = by_id[table_id]
            candidate["status"] = "specialist_verified"
            candidate["specialist"] = details
    for item in blocked:
        for candidate in targets:
            if pages_for(item).intersection(candidate["pages"]):
                candidate["status"] = "specialist_blocked"
                candidate["routeReasons"].append(
                    f"page replacement blocked by an unaccepted specialist table: {item['parseTableId']}"
                )
    for item in invalid:
        item_pages = pages_for(item)
        affected = [candidate for candidate in targets if item_pages.intersection(candidate["pages"])]
        for candidate in affected:
            candidate["status"] = "specialist_failed"
            candidate["routeReasons"].extend(
                item.get("errors", []) or [f"specialist output {item.get('parseTableId')} was not accepted"]
            )
    blocked_ids = [item["parseTableId"] for item in blocked]
    unmatched = [
        item["parseTableId"] for item in valid
        if item["parseTableId"] not in used and item["parseTableId"] not in blocked_ids
    ]
    return {
        "pages": pages,
        "report": report,
        "replacements": replacements,
        "unmatched": unmatched,
        "failed": [item.get("parseTableId", "unknown") for item in invalid],
        "blocked": blocked_ids,
        "blockedPages": blocked_pages,
    }


def initialize_for_pages(pdf: Path, project: Path, pages: list[int]) -> None:
    try:
        initialize(pdf, project, pages=pages)
    except ValueError as exc:
        if "Project page selection is" not in str(exc):
            raise
        shutil.rmtree(project)
        initialize(pdf, project, pages=pages)


def plan_replacements(candidates: list[dict], items: list[dict]) -> tuple[list[dict], set[str]]:
    replacements: list[dict] = []
    used: set[str] = set()
    for index, group in enumerate(overlapping_item_groups(items), start=1):
        group_pages = set().union(*(pages_for(item) for item in group))
        affected = [candidate for candidate in candidates if group_pages.intersection(candidate["pages"])]
        if not affected:
            continue
        spans = sorted({tuple(span) for candidate in affected for span in candidate.get("spans", [])})
        bounds = sorted({tuple(bound) for candidate in affected for bound in candidate.get("pageBounds", [])})
        if not spans and not bounds:
            continue
        ordered = sorted(group, key=item_position)
        details = {
            "parseTableIds": [item["parseTableId"] for item in ordered],
            "titles": [item.get("title", "") for item in ordered],
            "pages": sorted(group_pages),
            "outputPaths": [item["outputPath"] for item in ordered],
            "textBefore": ordered[0].get("textBefore", ""),
            "textAfter": ordered[-1].get("textAfter", ""),
        }
        replacements.append(
            {
                "replacementId": f"specialist_{index:04d}",
                "spans": [list(span) for span in spans],
                "pageBounds": [list(bound) for bound in bounds],
                "replacementMarkdown": "\n\n".join(
                    csv_to_markdown(Path(item["outputPath"])) for item in ordered
                ),
                "affectedTableIds": [candidate["tableId"] for candidate in affected],
                "specialist": details,
            }
        )
        used.update(item["parseTableId"] for item in ordered)
    return replacements, used


def overlapping_item_groups(items: list[dict]) -> list[list[dict]]:
    remaining = sorted(items, key=item_position, reverse=True)
    groups: list[list[dict]] = []
    while remaining:
        group = [remaining.pop()]
        pages = pages_for(group[0])
        changed = True
        while changed:
            changed = False
            for item in remaining[:]:
                if pages.intersection(pages_for(item)):
                    group.append(item)
                    pages.update(pages_for(item))
                    remaining.remove(item)
                    changed = True
        groups.append(group)
    return groups


def item_position(item: dict) -> tuple[float, float, float]:
    parts = item.get("tables", [])
    positions = []
    for part in parts:
        bbox = part.get("bbox", [])
        positions.append((float(part.get("page", 0)), float(bbox[1]) if len(bbox) == 4 else 0.0,
                          float(bbox[0]) if len(bbox) == 4 else 0.0))
    return min(positions, default=(0.0, 0.0, 0.0))


def csv_to_markdown(path: Path) -> str:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream))
    if not rows or not rows[0]:
        raise ValueError(f"Specialist CSV is empty: {path}")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError(f"Specialist CSV is not rectangular: {path}")
    lines = [markdown_row(rows[0]), markdown_row(["---"] * width)]
    lines.extend(markdown_row(row) for row in rows[1:])
    return "\n".join(lines)


def markdown_row(row: list[str]) -> str:
    return "| " + " | ".join(escape_cell(value) for value in row) + " |"


def escape_cell(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>").replace("\r", "<br>")
