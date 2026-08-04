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
            records.append({
                "table_id": table["id"], "segment_id": segment["id"], "page": segment["page"],
                "bbox": segment["bbox"], "overlay": str(overlay),
                "overlay_sha256": artifact_hash(overlay),
                "blocking_signals": blocking, "advisory_signals": advisory,
                "suggested_bbox": _suggested_bbox(page.rect, fitz.Rect(*segment["bbox"]), blocking),
            })
    document.close()
    draft_hash = artifact_hash(draft_path)
    review_path = job.evidence_dir / "inventory-review.json"
    review = _review(job, review_path, draft_hash, records)
    decisions = {(x["table_id"], x["segment_id"]): x for x in review["segments"]}
    for record in records:
        decision = decisions.get((record["table_id"], record["segment_id"]), {})
        record["attested"] = (
            decision.get("overlay_sha256") == record["overlay_sha256"]
            and decision.get("all_visible_table_content_inside") is True
            and set(decision.get("reviewed_edges", [])) == EDGES
        )
        record["passed"] = record["attested"] and not record["blocking_signals"]
    report = {
        "spec": "pdf-extractor-pdf/inventory-audit@2.0", "source_sha256": source_sha256(job.source),
        "draft_sha256": draft_hash, "passed": all(x["passed"] for x in records),
        "review_path": str(review_path),
        "review_sha256": artifact_hash(review_path),
        "instructions": "Fix blocking bboxes, then set visible=true and all four edges in inventory-review.json; overlay hashes are code-bound.",
        "segments": records,
    }
    write_json(job.evidence_dir / "inventory-audit.json", report)
    update_phase(job.evidence_dir, "prepared", "inventory_audited", {
        "passed": report["passed"], "segment_count": len(records),
        "blocking_signal_count": sum(len(x["blocking_signals"]) for x in records),
    })
    return report


def _review(job: Job, path: Path, draft_hash: str, records: list[dict]) -> dict:
    existing = read_json(path) if path.is_file() else {}
    expected = [(x["table_id"], x["segment_id"], x["bbox"], x["overlay_sha256"]) for x in records]
    supplied = [
        (x.get("table_id"), x.get("segment_id"), x.get("bbox"), x.get("overlay_sha256"))
        for x in existing.get("segments", [])
    ]
    if existing.get("draft_sha256") == draft_hash and supplied == expected:
        return existing
    value = {
        "spec": "pdf-extractor-pdf/inventory-review@1.0", "draft_sha256": draft_hash,
        "instructions": "Finder edits only all_visible_table_content_inside and reviewed_edges.",
        "segments": [
            {
                "table_id": x["table_id"], "segment_id": x["segment_id"], "page": x["page"],
                "bbox": x["bbox"], "overlay": x["overlay"], "overlay_sha256": x["overlay_sha256"],
                "all_visible_table_content_inside": False, "reviewed_edges": [],
            }
            for x in records
        ],
    }
    write_json(path, value)
    return value


def _suggested_bbox(page: fitz.Rect, bbox: fitz.Rect, blocking: list[dict]) -> list[float] | None:
    if not blocking:
        return None
    suggested = fitz.Rect(bbox)
    for item in blocking:
        suggested.include_rect(fitz.Rect(*item["bbox"]))
    suggested = fitz.Rect(
        max(page.x0, suggested.x0 - 2), max(page.y0, suggested.y0 - 2),
        min(page.x1, suggested.x1 + 2), min(page.y1, suggested.y1 + 2),
    )
    return [round(value, 3) for value in suggested]


def require_inventory_audit(job: Job, draft_path: Path) -> dict:
    path = job.evidence_dir / "inventory-audit.json"
    if not path.is_file():
        raise ValueError("run audit-inventory and review every Segment overlay before freezing Inventory")
    report = read_json(path)
    if report.get("draft_sha256") != artifact_hash(draft_path):
        raise ValueError("Inventory draft changed after audit; rerun audit-inventory")
    review_path = Path(report.get("review_path", ""))
    if not review_path.is_file() or report.get("review_sha256") != artifact_hash(review_path):
        raise ValueError("Inventory review changed after audit; rerun audit-inventory")
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
    matrix = page.rotation_matrix
    for word in page.get_text("words"):
        rect = fitz.Rect(*word[:4]) * matrix
        if rect.intersects(bbox) and not bbox.contains(rect):
            blocking.append({"code": "clipped_word", "text": word[4], "bbox": list(rect)})
        edge = _near_edge(rect, bbox, 12)
        if edge:
            advisory.append({"code": "word_just_outside", "edge": edge, "text": word[4], "bbox": list(rect)})
    for drawing in page.get_drawings():
        for item in drawing.get("items", []):
            if item[0] == "l":
                start, end = item[1] * matrix, item[2] * matrix
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
