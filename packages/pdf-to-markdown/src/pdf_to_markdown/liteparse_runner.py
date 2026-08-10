from __future__ import annotations

from dataclasses import asdict
from math import floor, sqrt
from pathlib import Path

import pymupdf
from liteparse import LiteParse


DEFAULT_DPI = 150.0
MAX_RENDER_PIXELS = 25_000_000
MAX_RENDER_SIDE = 6_000


def parse_pdf(pdf: Path, *, image_output_dir: Path, workers: int | None = None) -> dict:
    image_output_dir.mkdir(parents=True, exist_ok=True)
    render_dpi = bounded_dpi(pdf)
    parser = LiteParse(
        dpi=render_dpi,
        output_format="markdown",
        include_complexity=True,
        extract_text_metadata=True,
        extract_vector_graphics=True,
        image_mode="placeholder",
        extract_images=True,
        image_output_dir=image_output_dir,
        num_workers=workers,
        quiet=True,
    )
    result = parser.parse(pdf)
    image_names = [image.name for image in result.images]
    pages = []
    for page in result.pages:
        pages.append(
            {
                "page": page.page_num,
                "width": page.width,
                "height": page.height,
                "markdown": relative_image_paths(page.markdown, image_output_dir.name, image_names),
                "textItems": [text_item(item) for item in page.text_items],
                "complexity": asdict(page.complexity) if page.complexity else None,
                "vectorLines": [asdict(line) for line in (page.vector_graphics.lines if page.vector_graphics else [])],
            }
        )
    return {
        "version": "pdf-to-markdown/liteparse@1.0",
        "renderDpi": render_dpi,
        "markdown": relative_image_paths(result.text, image_output_dir.name, image_names),
        "pages": pages,
    }


def bounded_dpi(pdf: Path, default: float = DEFAULT_DPI) -> float:
    """Cap LiteParse raster dimensions while keeping normal PDFs at full DPI."""
    document = pymupdf.open(pdf)
    try:
        limit = default
        for page in document:
            width, height = float(page.rect.width), float(page.rect.height)
            if width <= 0 or height <= 0:
                continue
            side_dpi = min(MAX_RENDER_SIDE / width, MAX_RENDER_SIDE / height) * 72
            pixel_dpi = sqrt(MAX_RENDER_PIXELS / (width * height)) * 72
            limit = min(limit, side_dpi, pixel_dpi)
        return floor(limit * 100) / 100
    finally:
        document.close()


def relative_image_paths(markdown: str, directory: str, names: list[str]) -> str:
    for name in names:
        markdown = markdown.replace(f"]({name})", f"]({directory}/{name})")
    return markdown


def text_item(item) -> dict:
    return {
        "text": item.text,
        "x": item.x,
        "y": item.y,
        "width": item.width,
        "height": item.height,
        "rotation": item.rotation,
        "confidence": item.confidence,
    }
