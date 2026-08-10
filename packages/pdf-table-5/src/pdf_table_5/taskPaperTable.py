from __future__ import annotations

from .context import Context
from .io import read_json, relative, write_json
from .pdf import extract_page_geometry, render_page


def run(context: Context, listed: dict) -> dict:
    table_id = listed["parseTableId"]
    table_dir = context.paths.table_dir(table_id)
    table_dir.mkdir(parents=True, exist_ok=True)
    pages = {item["page"]: item for item in read_json(context.paths.helper_json("taskPaperFindTables.json"), {}).get("pages", [])}
    margin = float(context.params.get("bboxMarginPt", 72))
    segments = []
    for index, source in enumerate(listed["tables"], start=1):
        page = source["page"]
        source_bbox = tuple(source["bbox"])
        bbox = expanded_bbox(source_bbox, pages[page], margin)
        dpi = int(source.get("recommendedDpi") or context.params.get("tableDpi", 216))
        image = table_dir / f"segment-{index:02d}-p{page:04d}.png"
        context_image = table_dir / f"segment-{index:02d}-p{page:04d}-context.png"
        geometry = table_dir / f"segment-{index:02d}-p{page:04d}.json"
        table_render = render_page(context.pdf, page, image, dpi, bbox)
        context_render = render_page(context.pdf, page, context_image, min(dpi, 144))
        extract_page_geometry(context.pdf, page, geometry, bbox)
        segments.append(
            {
                **source,
                "sourceBbox": list(source_bbox),
                "bbox": list(bbox),
                "screenshot": relative(image, context.paths.project),
                "contextScreenshot": relative(context_image, context.paths.project),
                "geometry": relative(geometry, context.paths.project),
                "extractionDpi": dpi,
                "screenshotPixels": {"width": table_render["widthPx"], "height": table_render["heightPx"]},
                "contextPixels": {"width": context_render["widthPx"], "height": context_render["heightPx"]},
            }
        )
    packet = {
        "version": "pdf-table-5/table-packet@1.0",
        "parseTableId": table_id,
        "findTableIds": listed["findTableIds"],
        "titleHint": listed.get("titleHint", ""),
        "sourcePdf": str(context.pdf),
        "projectRoot": str(context.paths.project.resolve()),
        "coordinateSystem": {
            "name": "visual-page", "origin": "top-left", "xDirection": "right", "yDirection": "down", "unit": "pt"
        },
        "tables": segments,
    }
    write_json(table_dir / "table.json", packet)
    return packet


def expanded_bbox(bbox: tuple[float, ...], page: dict, margin: float) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = bbox
    return (
        max(0.0, x0 - margin),
        max(0.0, y0 - margin),
        min(float(page["width"]), x1 + margin),
        min(float(page["height"]), y1 + margin),
    )
