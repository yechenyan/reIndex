from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from liteparse import LiteParse

from .chrome import mark_repeated_page_chrome
from .constants import FORMAT_VERSION
from .io_utils import atomic_json
from .markdown import liteparse_block_markdown
from .native_geometry import page_geometry
from .paths import ProjectPaths


def _rect(value: Any) -> list[float] | None:
    if value is None:
        return None
    return [value.x, value.y, value.width, value.height]


def _cell(cell: Any) -> dict[str, Any]:
    return {"text": cell.text, "bbox": _rect(cell.bbox)}


def _block(block: Any, page_num: int, order: int) -> dict[str, Any]:
    item = {
        "blockId": f"p{page_num:04d}-b{order:04d}",
        "page": page_num,
        "order": order,
        "bbox": _rect(block.bbox),
        "liteParseType": block.kind,
        "preType": block.kind,
        "text": block.text,
        "markdown": liteparse_block_markdown(block),
        "ignored": False,
        "ignoredReason": None,
        "needsAgent": block.kind in {"table", "figure", "grid_fallback"},
    }
    if block.kind == "table":
        item["table"] = {
            "header": [_cell(cell) for cell in (block.header or [])],
            "rows": [[_cell(cell) for cell in row] for row in (block.rows or [])],
        }
    if block.kind == "figure":
        item["figureId"] = block.id
        item["figureFormat"] = block.format
    return item


def parse_document(paths: ProjectPaths, pdf_path: Path) -> dict[str, Any]:
    image_dir = paths.assets / "source-images"
    image_dir.mkdir(parents=True, exist_ok=True)
    parser = LiteParse(
        ocr_enabled=False,
        output_format="markdown",
        extract_blocks=True,
        emit_word_boxes=True,
        include_complexity=True,
        extract_vector_graphics=True,
        extract_content_bounds=True,
        extract_images=True,
        image_output_dir=image_dir,
        continue_on_page_error=True,
        ocr_failure_fatal=False,
        quiet=True,
    )
    result = parser.parse(pdf_path)
    pages = []
    for page in result.pages:
        complexity = asdict(page.complexity) if page.complexity else None
        blocks = [_block(block, page.page_num, index) for index, block in enumerate(page.blocks or [])]
        page_data = {
            "page": page.page_num,
            "widthPt": page.width,
            "heightPt": page.height,
            "markdown": page.markdown,
            "contentBounds": page.content_bounds,
            "complexity": complexity,
            "blocks": blocks,
        }
        pages.append(page_data)
        atomic_json(
            paths.helper / "native-geometry" / f"page-{page.page_num:04d}.json",
            page_geometry(page),
        )
    mark_repeated_page_chrome(pages)
    _add_page_level_uncertainty(pages)
    document = {
        "formatVersion": FORMAT_VERSION,
        "totalPages": result.total_pages,
        "pageErrors": [asdict(error) for error in result.page_errors],
        "pages": pages,
        "images": [_image_data(image) for image in result.images],
    }
    atomic_json(paths.helper / "liteparse.json", document)
    atomic_json(paths.helper / "documentBlocks.json", [block for page in pages for block in page["blocks"]])
    return document


def _image_data(image: Any) -> dict[str, Any]:
    return {
        "id": image.id,
        "page": image.page,
        "bbox": _rect(image.bbox),
        "width": image.width,
        "height": image.height,
        "format": image.format,
        "path": str(image.path) if image.path else None,
        "duplicateOf": getattr(image, "duplicate_of", None),
    }


def _add_page_level_uncertainty(pages: list[dict[str, Any]]) -> None:
    severe = {"scanned", "no-text", "garbled", "vector-text", "annotation-text"}
    for page in pages:
        complexity = page.get("complexity") or {}
        reasons = set(complexity.get("reasons") or [])
        active = [block for block in page["blocks"] if not block["ignored"]]
        if reasons & severe and not any(block["needsAgent"] for block in active):
            page["blocks"].append(
                {
                    "blockId": f"p{page['page']:04d}-uncertain-page",
                    "page": page["page"],
                    "order": len(page["blocks"]),
                    "bbox": [0.0, 0.0, page["widthPt"], page["heightPt"]],
                    "liteParseType": "uncertain_page",
                    "preType": "uncertain_page",
                    "text": None,
                    "markdown": page["markdown"],
                    "ignored": False,
                    "ignoredReason": None,
                    "needsAgent": True,
                }
            )
