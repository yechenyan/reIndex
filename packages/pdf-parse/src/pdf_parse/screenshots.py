from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any

from liteparse import LiteParse
from PIL import Image

from .io_utils import atomic_json, read_json
from .paths import ProjectPaths


def bounded_dpi(
    requested: float,
    page_width: float,
    page_height: float,
    params: dict[str, Any],
) -> float:
    config = params["screenshots"]
    dpi = min(max(requested, config["minDpi"]), config["maxDpi"])
    long_limit = config["maxImageSide"] * 72 / max(page_width, page_height)
    pixel_limit = math.sqrt(config["maxImagePixels"] * 72 * 72 / (page_width * page_height))
    return round(min(dpi, long_limit, pixel_limit), 2)


class ScreenshotService:
    def __init__(self, paths: ProjectPaths, pdf_path: Path):
        self.paths = paths
        self.pdf_path = pdf_path
        self.params = read_json(paths.params)
        self.pages = {
            page["page"]: page for page in read_json(paths.helper / "liteparse.json")["pages"]
        }

    def page(self, page_num: int, requested_dpi: float, label: str) -> dict[str, Any]:
        page = self.pages[page_num]
        dpi = bounded_dpi(requested_dpi, page["widthPt"], page["heightPt"], self.params)
        cache = self.paths.helper / "screenshots" / f"page-{page_num:04d}-{dpi:g}.png"
        if not cache.exists():
            shot = LiteParse(ocr_enabled=False, dpi=dpi, quiet=True).screenshot(
                self.pdf_path, page_numbers=[page_num]
            )[0]
            cache.write_bytes(shot.image_bytes)
        with Image.open(cache) as image:
            width, height = image.size
        target = self.paths.helper / "screenshots" / label
        if target != cache:
            target.write_bytes(cache.read_bytes())
        return {
            "path": str(target),
            "page": page_num,
            "requestedDpi": requested_dpi,
            "actualDpi": dpi,
            "pixels": {"width": width, "height": height},
            "bboxPt": [0.0, 0.0, page["widthPt"], page["heightPt"]],
        }

    def crop(
        self,
        page_num: int,
        bbox: list[float],
        requested_dpi: float,
        target: Path,
    ) -> dict[str, Any]:
        evidence = self.page(page_num, requested_dpi, f"cache-crop-source-{page_num}.png")
        page = self.pages[page_num]
        source = Path(evidence["path"])
        with Image.open(source) as image:
            x_scale = image.width / page["widthPt"]
            y_scale = image.height / page["heightPt"]
            x, y, width, height = clamp_bbox(bbox, page["widthPt"], page["heightPt"])
            pixels = (
                round(x * x_scale),
                round(y * y_scale),
                round((x + width) * x_scale),
                round((y + height) * y_scale),
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            image.crop(pixels).save(target)
            size = Image.open(target).size
        return {
            "path": str(target),
            "page": page_num,
            "requestedDpi": requested_dpi,
            "actualDpi": evidence["actualDpi"],
            "pixels": {"width": size[0], "height": size[1]},
            "bboxPt": [x, y, width, height],
        }


def clamp_bbox(bbox: list[float], page_width: float, page_height: float) -> list[float]:
    x, y, width, height = bbox
    left = max(0.0, x)
    top = max(0.0, y)
    right = min(page_width, x + width)
    bottom = min(page_height, y + height)
    return [left, top, max(0.0, right - left), max(0.0, bottom - top)]


def write_evidence_manifest(path: Path, evidence: list[dict[str, Any]]) -> None:
    atomic_json(path, {"images": evidence})
