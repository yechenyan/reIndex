from __future__ import annotations

import io
import math
from pathlib import Path

import pymupdf
from PIL import Image, ImageChops, ImageStat

from .io import sha256
from .page_selection import PageSelection, normalize_pages

Rect = tuple[float, float, float, float]


def open_pdf(path: Path) -> pymupdf.Document:
    try:
        document = pymupdf.open(path)
    except Exception as exc:
        raise ValueError(f"Unreadable PDF: {path}: {exc}") from exc
    if not document.is_pdf or document.needs_pass:
        document.close()
        raise ValueError(f"Invalid or password-protected PDF: {path}")
    return document


def inspect_pdf(path: Path, target_pages: PageSelection = None) -> dict:
    document = open_pdf(path)
    try:
        pages = []
        selected = normalize_pages(target_pages, document.page_count)
        page_numbers = selected or list(range(1, document.page_count + 1))
        for page_number in page_numbers:
            index = page_number - 1
            page = document.load_page(index)
            entry = {
                "page": index + 1,
                "width": round(page.rect.width, 3),
                "height": round(page.rect.height, 3),
                "sourceRotation": page.rotation,
                "skipFinder": False,
                "skipReason": "",
            }
            try:
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(0.25, 0.25), alpha=False)
                image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("L")
                text = page.get_text("text").strip()
                extrema = ImageStat.Stat(ImageChops.invert(image)).extrema[0]
                if not text and extrema[1] <= 2:
                    entry.update(skipFinder=True, skipReason="programmatically blank page")
            except Exception as exc:
                entry.update(skipFinder=True, skipReason=f"render failure: {exc}")
            pages.append(entry)
        return {
            "isValidPdf": True,
            "totalPages": document.page_count,
            "sha256": sha256(path),
            "pageNumbering": "1-based",
            "coordinateSystem": visual_coordinates(),
            "pages": pages,
        }
    finally:
        document.close()


def visual_coordinates() -> dict:
    return {
        "name": "visual-page",
        "origin": "top-left",
        "xDirection": "right",
        "yDirection": "down",
        "unit": "pt",
    }


def render_page(pdf: Path, page_number: int, output: Path, dpi: int, bbox: Rect | None = None) -> dict:
    document = open_pdf(pdf)
    try:
        if not 1 <= page_number <= document.page_count:
            raise ValueError(f"Page {page_number} outside 1..{document.page_count}")
        page = document.load_page(page_number - 1)
        scale = dpi / 72
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
        used = (0.0, 0.0, page.rect.width, page.rect.height)
        if bbox is not None:
            used = validate_bbox(bbox, page.rect.width, page.rect.height)
            pixels = tuple(round(value * scale) for value in used)
            image = image.crop(pixels)
        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output)
        return {"page": page_number, "dpi": dpi, "bbox": list(used), "widthPx": image.width, "heightPx": image.height}
    finally:
        document.close()


def validate_bbox(bbox: Rect, width: float, height: float) -> Rect:
    if len(bbox) != 4:
        raise ValueError("bbox must contain x0, y0, x1, y1")
    x0, y0, x1, y1 = map(float, bbox)
    values = (max(0.0, x0), max(0.0, y0), min(width, x1), min(height, y1))
    if values[2] <= values[0] or values[3] <= values[1]:
        raise ValueError(f"Empty bbox after clipping: {bbox}")
    return values


def visual_rect(page: pymupdf.Page, raw) -> list[float]:
    rect = pymupdf.Rect(raw) * page.rotation_matrix
    return [round(rect.x0, 3), round(rect.y0, 3), round(rect.x1, 3), round(rect.y1, 3)]


def extract_page_geometry(pdf: Path, page_number: int, output: Path, bbox: Rect | None = None) -> None:
    document = open_pdf(pdf)
    try:
        page = document.load_page(page_number - 1)
        words = []
        for item in page.get_text("words", sort=False):
            visual = visual_rect(page, item[:4])
            if bbox is not None and not center_in(visual, bbox):
                continue
            words.append({"bbox": visual, "text": item[4], "block": item[5], "line": item[6], "word": item[7]})
        images = [visual_rect(page, item["bbox"]) for item in page.get_image_info()]
        output.parent.mkdir(parents=True, exist_ok=True)
        from .io import write_json
        write_json(output, {"page": page_number, "width": page.rect.width, "height": page.rect.height, "words": words, "images": images})
    finally:
        document.close()


def center_in(rect: list[float], bbox: Rect) -> bool:
    x, y = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
    return bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]


def sheet_shape(page_count: int) -> dict:
    columns = max(1, min(4, math.ceil(math.sqrt(page_count * 0.7))))
    return {"columns": columns, "rowsPerSheet": max(1, 12 // columns), "maxPagesPerSheet": 12}
