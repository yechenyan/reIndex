from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_cli import AgentError, run_agent
from .geometry import expanded_bbox
from .io_utils import atomic_json, read_json
from .paths import ProjectPaths
from .prompts import compose, load_prompt
from .screenshots import ScreenshotService


def classify_blocks(paths: ProjectPaths, pdf_path: Path) -> dict[str, Any]:
    document = read_json(paths.helper / "liteparse.json")
    blocks = [
        block
        for page in document["pages"]
        for block in page["blocks"]
        if block["needsAgent"] and not block["ignored"]
    ]
    if not blocks:
        result = {"items": [], "warnings": []}
        atomic_json(paths.helper / "classifiedBlocks.json", result)
        return {"result": result, "usage": {}}
    pages = sorted({block["page"] for block in blocks})
    shots = ScreenshotService(paths, pdf_path)
    screenshot_config = read_json(paths.params)["screenshots"]
    classify_dpi = min(300, screenshot_config["maxDpi"])
    evidence = []
    images: list[Path] = []
    page_data = {page["page"]: page for page in document["pages"]}
    for page in pages:
        overview = shots.page(page, classify_dpi, f"classify-page-{page:04d}.png")
        dimensions = page_data[page]
        region = expanded_bbox(
            _union_bbox([block["bbox"] for block in blocks if block["page"] == page]),
            dimensions["widthPt"],
            dimensions["heightPt"],
            8.0,
        )
        crop = shots.crop(
            page,
            region,
            classify_dpi,
            paths.helper / "screenshots" / f"classify-region-{page:04d}.png",
        )
        overview["visualOrder"] = "full-page overview"
        crop["visualOrder"] = "high-resolution union of uncertain block regions"
        evidence.extend([overview, crop])
        images.extend([Path(overview["path"]), Path(crop["path"])])
    context = {
        "pages": [
            {
                "page": page["page"],
                "widthPt": page["widthPt"],
                "heightPt": page["heightPt"],
            }
            for page in document["pages"]
            if page["page"] in pages
        ],
        "blocks": [_agent_block(block, blocks) for block in blocks],
        "evidence": evidence,
    }
    params = read_json(paths.params)["agents"]
    prompt = compose(load_prompt("base.md"), load_prompt("classify.md"), context=context)
    try:
        agent = run_agent(
            project_root=paths.root,
            prompt=prompt,
            images=images,
            schema_name="classify.json",
            model=params["model"],
            reasoning=params["reasoningEffort"],
        )
        result = _validate(agent.data, blocks, document)
        usage = agent.usage
        result["agentSessionId"] = agent.session_id
        if agent.stderr:
            (paths.report / "classify-agent.stderr.log").write_text(agent.stderr, encoding="utf-8")
    except (AgentError, ValueError) as exc:
        result = _fallback(blocks, f"Classifier fallback: {exc}")
        usage = {}
    atomic_json(paths.helper / "classifiedBlocks.json", result)
    return {"result": result, "usage": usage}


def _agent_block(block: dict[str, Any], all_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    table = block.get("table") or {}
    rows = table.get("rows") or []
    nonempty = [
        [cell["text"] for cell in row]
        for row in rows
        if any((cell.get("text") or "").strip() for cell in row)
    ]
    return {
        "blockId": block["blockId"],
        "page": block["page"],
        "bbox": block["bbox"],
        "preType": block["preType"],
        "textPreview": (block.get("text") or block.get("markdown") or "")[:1200],
        "tableShape": {
            "headerCells": len(table.get("header") or []),
            "rows": len(rows),
            "columnCounts": sorted({len(row) for row in rows}),
            "firstNonEmptyRows": nonempty[:2],
            "lastNonEmptyRows": nonempty[-2:],
        }
        if table
        else None,
        "overlaps": [
            other["blockId"]
            for other in all_blocks
            if other["blockId"] != block["blockId"]
            and other["page"] == block["page"]
            and _intersects(block["bbox"], other["bbox"])
        ],
    }


def _validate(
    result: dict[str, Any],
    blocks: list[dict[str, Any]],
    document: dict[str, Any],
) -> dict[str, Any]:
    expected = {block["blockId"] for block in blocks}
    seen = {source for item in result.get("items", []) for source in item["sourceBlockIds"]}
    if not expected.issubset(seen):
        raise ValueError(f"Classifier omitted blocks: {sorted(expected - seen)}")
    sizes = {page["page"]: (page["widthPt"], page["heightPt"]) for page in document["pages"]}
    for item in result["items"]:
        if not set(item["sourceBlockIds"]).issubset(expected):
            raise ValueError("Classifier returned an unknown source block")
        x, y, width, height = item["bbox"]
        page_width, page_height = sizes[item["page"]]
        if min(x, y, width, height) < 0 or x + width > page_width + 1 or y + height > page_height + 1:
            raise ValueError(f"Classifier bbox outside page: {item['classifyBlockId']}")
    return result


def _intersects(left: list[float], right: list[float]) -> bool:
    lx, ly, lw, lh = left
    rx, ry, rw, rh = right
    return lx < rx + rw and lx + lw > rx and ly < ry + rh and ly + lh > ry


def _union_bbox(boxes: list[list[float]]) -> list[float]:
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[0] + box[2] for box in boxes)
    bottom = max(box[1] + box[3] for box in boxes)
    return [left, top, right - left, bottom - top]


def _fallback(blocks: list[dict[str, Any]], warning: str) -> dict[str, Any]:
    items = []
    mapping = {"table": "table", "figure": "figure", "grid_fallback": "text"}
    for index, block in enumerate(blocks):
        items.append(
            {
                "classifyBlockId": f"c{index + 1:04d}",
                "sourceBlockIds": [block["blockId"]],
                "page": block["page"],
                "bbox": block["bbox"],
                "preType": block["preType"],
                "classifyType": mapping.get(block["preType"], "figure"),
                "canMergePrevious": False,
                "confidence": 0.0,
                "note": warning,
            }
        )
    return {"items": items, "warnings": [warning]}
