from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

from pdf_extractor_pdf.artifacts import artifact_hash, read_json, write_json
from pdf_extractor_pdf.inventory import _validate_draft
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.models import source_sha256
from pdf_extractor_pdf.workflow import require_phase, update_phase

EDGES = {"left", "right", "top", "bottom"}


def audit_inventory(job: Job, draft_path: Path) -> dict:
    require_phase(job.evidence_dir, "prepared")
    draft = read_json(draft_path)
    document = fitz.open(job.source)
    _validate_draft(draft, job, document)
    records = []
    for table in draft["tables"]:
        for segment in table["segments"]:
            page = document[segment["page"] - 1]
            overlay = _overlay(job, page, table["id"], segment)
            blocking, advisory = _edge_signals(page, fitz.Rect(*segment["bbox"]))
            review = segment.get("bbox_review", {})
            attested = (
                review.get("overlay_sha256") == artifact_hash(overlay)
                and review.get("all_visible_table_content_inside") is True
                and set(review.get("reviewed_edges", [])) == EDGES
            )
            records.append({
                "table_id": table["id"], "segment_id": segment["id"], "page": segment["page"],
                "bbox": segment["bbox"], "overlay": str(overlay),
                "overlay_sha256": artifact_hash(overlay), "attested": attested,
                "blocking_signals": blocking, "advisory_signals": advisory,
                "passed": attested and not blocking,
            })
    document.close()
    report = {
        "spec": "pdf-extractor-pdf/inventory-audit@1.0", "source_sha256": source_sha256(job.source),
        "draft_sha256": artifact_hash(draft_path), "passed": all(x["passed"] for x in records),
        "instructions": "Review each full-page overlay and copy its SHA into bbox_review after checking all four edges.",
        "segments": records,
    }
    write_json(job.evidence_dir / "inventory-audit.json", report)
    update_phase(job.evidence_dir, "prepared", "inventory_audited", {
        "passed": report["passed"], "segment_count": len(records),
        "blocking_signal_count": sum(len(x["blocking_signals"]) for x in records),
    })
    return report


def require_inventory_audit(job: Job, draft_path: Path) -> dict:
    path = job.evidence_dir / "inventory-audit.json"
    if not path.is_file():
        raise ValueError("run audit-inventory and review every Segment overlay before freezing Inventory")
    report = read_json(path)
    if report.get("draft_sha256") != artifact_hash(draft_path):
        raise ValueError("Inventory draft changed after audit; rerun audit-inventory")
    if report.get("source_sha256") != source_sha256(job.source) or not report.get("passed"):
        raise ValueError("Inventory audit has unreviewed or clipped Segment bounds")
    return report


def _overlay(job: Job, page: fitz.Page, table_id: str, segment: dict) -> Path:
    dpi = int(job.evidence.get("inventory_overlay_dpi", 110))
    key = json.dumps({
        "table": table_id, "segment": segment["id"], "page": segment["page"],
        "bbox": segment["bbox"], "dpi": dpi,
    }, sort_keys=True, ensure_ascii=False).encode()
    stem = f"{segment['id']}-{hashlib.sha256(key).hexdigest()[:12]}-page-{segment['page']:04d}.png"
    path = job.evidence_dir / "inventory-overlays" / table_id / stem
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        return path
    pixmap = page.get_pixmap(dpi=dpi, alpha=False)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    sx, sy = pixmap.width / page.rect.width, pixmap.height / page.rect.height
    x0, y0, x1, y1 = segment["bbox"]
    draw = ImageDraw.Draw(image)
    box = [round(x0 * sx), round(y0 * sy), round(x1 * sx), round(y1 * sy)]
    draw.rectangle(box, outline=(255, 0, 0), width=5)
    draw.rectangle([box[0], max(0, box[1] - 22), box[0] + 240, box[1]], fill=(255, 255, 255))
    draw.text((box[0] + 4, max(0, box[1] - 19)), f"{table_id} / {segment['id']}", fill=(200, 0, 0))
    image.save(path)
    return path


def _edge_signals(page: fitz.Page, bbox: fitz.Rect) -> tuple[list[dict], list[dict]]:
    blocking, advisory = [], []
    for word in page.get_text("words"):
        rect = fitz.Rect(*word[:4])
        if rect.intersects(bbox) and not bbox.contains(rect):
            blocking.append({"code": "clipped_word", "text": word[4], "bbox": list(rect)})
        edge = _near_edge(rect, bbox, 12)
        if edge:
            advisory.append({"code": "word_just_outside", "edge": edge, "text": word[4], "bbox": list(rect)})
    for drawing in page.get_drawings():
        for item in drawing.get("items", []):
            if item[0] == "l":
                start, end = item[1], item[2]
                if _line_crosses(start, end, bbox):
                    advisory.append({"code": "drawing_crosses_bbox", "from": [start.x, start.y], "to": [end.x, end.y]})
    return _dedupe(blocking), _dedupe(advisory)[:40]


def _near_edge(rect: fitz.Rect, bbox: fitz.Rect, margin: float) -> str | None:
    vertical_overlap = rect.y1 >= bbox.y0 and rect.y0 <= bbox.y1
    horizontal_overlap = rect.x1 >= bbox.x0 and rect.x0 <= bbox.x1
    if vertical_overlap and bbox.x1 <= rect.x0 <= bbox.x1 + margin:
        return "right"
    if vertical_overlap and bbox.x0 - margin <= rect.x1 <= bbox.x0:
        return "left"
    if horizontal_overlap and bbox.y1 <= rect.y0 <= bbox.y1 + margin:
        return "bottom"
    if horizontal_overlap and bbox.y0 - margin <= rect.y1 <= bbox.y0:
        return "top"
    return None


def _line_crosses(start: fitz.Point, end: fitz.Point, bbox: fitz.Rect) -> bool:
    start_inside, end_inside = bbox.contains(start), bbox.contains(end)
    if start_inside != end_inside:
        return True
    x0, x1 = sorted((start.x, end.x))
    y0, y1 = sorted((start.y, end.y))
    crosses_horizontal = y0 <= bbox.y1 and y1 >= bbox.y0 and x0 < bbox.x0 < x1
    crosses_horizontal |= y0 <= bbox.y1 and y1 >= bbox.y0 and x0 < bbox.x1 < x1
    crosses_vertical = x0 <= bbox.x1 and x1 >= bbox.x0 and y0 < bbox.y0 < y1
    crosses_vertical |= x0 <= bbox.x1 and x1 >= bbox.x0 and y0 < bbox.y1 < y1
    return bool(crosses_horizontal or crosses_vertical)


def _dedupe(values: list[dict]) -> list[dict]:
    seen, result = set(), []
    for value in values:
        key = json.dumps(value, sort_keys=True)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result
