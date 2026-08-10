from __future__ import annotations

import io
from pathlib import Path

import pymupdf
from PIL import Image


def render_candidates(pdf: Path, candidates: list[dict], output: Path, dpi: int = 216) -> dict[str, list[Path]]:
    output.mkdir(parents=True, exist_ok=True)
    images: dict[str, list[Path]] = {}
    document = pymupdf.open(pdf)
    try:
        for candidate in candidates:
            if candidate["route"] != "sample":
                continue
            paths = []
            for page_number, bbox in zip(candidate["pages"], candidate["bboxes"]):
                target = output / f"{candidate['tableId']}-p{page_number:04d}.png"
                render(document, page_number, bbox, target, dpi)
                paths.append(target)
            images[candidate["tableId"]] = paths
    finally:
        document.close()
    return images


def render(document: pymupdf.Document, page_number: int, bbox: list[float], output: Path, dpi: int) -> None:
    page = document.load_page(page_number - 1)
    scale = dpi / 72
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
    x0, y0, x1, y1 = clipped(bbox, page.rect.width, page.rect.height)
    image.crop(tuple(round(value * scale) for value in (x0, y0, x1, y1))).save(output)


def clipped(bbox: list[float], width: float, height: float) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = map(float, bbox)
    value = max(0.0, x0), max(0.0, y0), min(width, x1), min(height, y1)
    if value[2] <= value[0] or value[3] <= value[1]:
        raise ValueError(f"Empty screenshot bbox: {bbox}")
    return value
