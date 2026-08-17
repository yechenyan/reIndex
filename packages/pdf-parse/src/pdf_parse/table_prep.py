from __future__ import annotations

from pathlib import Path
from typing import Any

from .constants import TABLE_CONTEXT_MARGIN_PT
from .geometry import expanded_bbox
from .io_utils import atomic_json, read_json
from .native_geometry import scoped_geometry
from .paths import ProjectPaths
from .screenshots import ScreenshotService


def table_items(classified: dict[str, Any]) -> list[dict[str, Any]]:
    items = [
        item
        for item in classified["items"]
        if item["classifyType"] in {"table", "image_table"}
    ]
    return sorted(items, key=lambda item: (item["page"], item["bbox"][1], item["bbox"][0]))


def merge_candidates(items: list[dict[str, Any]], index: int) -> list[dict[str, Any]]:
    current = items[index]
    candidates = [current]
    last_page = current["page"]
    for item in items[index + 1 :]:
        if not item["canMergePrevious"] or item["page"] > last_page + 1:
            break
        candidates.append(item)
        last_page = item["page"]
    return candidates


def prepare_table(
    paths: ProjectPaths,
    pdf_path: Path,
    table_id: str,
    candidates: list[dict[str, Any]],
    requested_dpi: float,
) -> tuple[dict[str, Any], list[Path]]:
    directory = paths.blocks / table_id
    directory.mkdir(parents=True, exist_ok=True)
    blocks = {block["blockId"]: block for block in read_json(paths.helper / "documentBlocks.json")}
    pages = {page["page"]: page for page in read_json(paths.helper / "liteparse.json")["pages"]}
    shots = ScreenshotService(paths, pdf_path)
    prepared = []
    for candidate in candidates:
        source_blocks = [blocks[source] for source in candidate["sourceBlockIds"]]
        page = pages[candidate["page"]]
        crop_bbox = expanded_bbox(
            candidate["bbox"],
            page["widthPt"],
            page["heightPt"],
            TABLE_CONTEXT_MARGIN_PT,
        )
        prepared.append(
            {
                **candidate,
                "cropBbox": crop_bbox,
                "sourceBlockIds": [block["blockId"] for block in source_blocks],
            }
        )
    evidence = []
    images: list[Path] = []
    for page_num, crop_bbox in _logical_regions(prepared):
        overview = shots.page(page_num, 96, f"{table_id}-p{page_num:04d}-overview.png")
        crop = shots.crop(
            page_num,
            crop_bbox,
            requested_dpi,
            directory / f"whole-table-p{page_num:04d}.png",
        )
        crop["visualOrder"] = "target anchor plus surrounding visual context"
        evidence.extend([overview, crop])
        images.extend([Path(overview["path"]), Path(crop["path"])])
    runtime_context = {
        "parseBlockId": table_id,
        "pdfPath": str(pdf_path),
        "requestedDpi": requested_dpi,
        "blocks": prepared,
    }
    pre_table = {
        **runtime_context,
        "dpiBounds": read_json(paths.params)["screenshots"],
        "evidence": evidence,
        "latestGeometry": scoped_geometry(paths, _logical_regions(prepared)),
    }
    atomic_json(directory / "preTable.json", runtime_context)
    atomic_json(directory / "agentContext.json", pre_table)
    return pre_table, images


def _logical_regions(prepared: list[dict[str, Any]]) -> list[tuple[int, list[float]]]:
    by_page: dict[int, list[list[float]]] = {}
    for item in prepared:
        by_page.setdefault(item["page"], []).append(item["cropBbox"])
    regions = []
    for page, boxes in sorted(by_page.items()):
        left = min(box[0] for box in boxes)
        top = min(box[1] for box in boxes)
        right = max(box[0] + box[2] for box in boxes)
        bottom = max(box[1] + box[3] for box in boxes)
        regions.append((page, [left, top, right - left, bottom - top]))
    return regions
