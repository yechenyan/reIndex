from __future__ import annotations

import json
import shutil
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any

import fitz
from PIL import Image

from pdf_table_codegen.job import Job
from pdf_table_codegen.models import source_sha256


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")


def _point(value: Any) -> tuple[float, float]:
    return float(value.x), float(value.y)


def _line(x0: float, y0: float, x1: float, y1: float) -> dict[str, Any]:
    delta_x, delta_y = abs(x1 - x0), abs(y1 - y0)
    orientation = "horizontal" if delta_y < 0.5 else "vertical" if delta_x < 0.5 else "other"
    return {
        "orientation": orientation,
        "points": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
        "length": round((delta_x * delta_x + delta_y * delta_y) ** 0.5, 2),
    }


def _drawing_lines(page: fitz.Page, clip: fitz.Rect) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for drawing in page.get_drawings():
        for item in drawing.get("items", []):
            if item[0] == "l":
                x0, y0 = _point(item[1])
                x1, y1 = _point(item[2])
                candidates = [_line(x0, y0, x1, y1)]
            elif item[0] == "re":
                rect = item[1]
                candidates = [
                    _line(rect.x0, rect.y0, rect.x1, rect.y0),
                    _line(rect.x1, rect.y0, rect.x1, rect.y1),
                    _line(rect.x1, rect.y1, rect.x0, rect.y1),
                    _line(rect.x0, rect.y1, rect.x0, rect.y0),
                ]
            else:
                continue
            for candidate in candidates:
                x0, y0, x1, y1 = candidate["points"]
                if fitz.Rect(min(x0, x1), min(y0, y1), max(x0, x1) + 0.1, max(y0, y1) + 0.1).intersects(clip):
                    lines.append(candidate)
    return lines


def _clusters(values: list[float], limit: int = 40) -> list[dict[str, Any]]:
    counts = Counter(round(value, 1) for value in values)
    return [{"position": key, "count": count} for key, count in counts.most_common(limit)]


def _segment_report(page: fitz.Page, bbox: list[float]) -> dict[str, Any]:
    clip = fitz.Rect(bbox)
    words = [word for word in page.get_text("words", sort=True) if clip.contains(fitz.Point((word[0] + word[2]) / 2, (word[1] + word[3]) / 2))]
    lines = _drawing_lines(page, clip)
    return {
        "bbox": [round(value, 2) for value in bbox],
        "word_count": len(words),
        "words": [[round(value, 2) if isinstance(value, float) else value for value in word] for word in words],
        "coordinate_clusters": {
            "word_x0": _clusters([word[0] for word in words]),
            "word_x1": _clusters([word[2] for word in words]),
            "word_y0": _clusters([word[1] for word in words]),
            "word_y1": _clusters([word[3] for word in words]),
        },
        "drawing_lines": lines,
        "horizontal_line_positions": _clusters([line["points"][1] for line in lines if line["orientation"] == "horizontal"]),
        "vertical_line_positions": _clusters([line["points"][0] for line in lines if line["orientation"] == "vertical"]),
        "notice": "Neutral source geometry only; choose the extraction strategy independently.",
    }


def inspect_inventory(job: Job) -> dict[str, Any]:
    inventory = json.loads(job.inventory.read_text(encoding="utf-8"))
    inventory_sha = source_sha256(job.inventory)
    if inventory.get("source_sha256") != source_sha256(job.source):
        raise ValueError("inventory does not match the current source")
    target_root = job.evidence_dir / "tables"
    if target_root.exists():
        shutil.rmtree(target_root)
    outputs: list[dict[str, Any]] = []
    dpi = int(job.evidence.get("table_dpi", max(180, int(job.evidence.get("page_dpi", 144)))))
    with fitz.open(job.source) as document:
        for table in inventory.get("tables", []):
            table_dir = target_root / table["id"]
            table_dir.mkdir(parents=True, exist_ok=True)
            segments = table.get("segments") or [{"page": page, "bbox": list(document[page - 1].rect)} for page in table["pages"]]
            for index, segment in enumerate(segments, start=1):
                page_number = int(segment["page"])
                bbox = [float(value) for value in segment["bbox"]]
                page = document[page_number - 1]
                pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), clip=fitz.Rect(bbox), alpha=False)
                image_name = f"segment-{index:02d}-page-{page_number:04d}.png"
                Image.open(BytesIO(pix.tobytes("png"))).convert("RGB").save(table_dir / image_name)
                report_name = f"segment-{index:02d}-page-{page_number:04d}.json"
                _write(table_dir / report_name, _segment_report(page, bbox))
                outputs.append({"table_id": table["id"], "page": page_number, "image": image_name, "geometry": report_name})
    manifest = {
        "spec": "pdf-table-codegen/table-evidence@1.0",
        "source_sha256": source_sha256(job.source),
        "inventory_sha256": inventory_sha,
        "dpi": dpi,
        "segments": outputs,
    }
    _write(target_root / "manifest.json", manifest)
    return manifest
