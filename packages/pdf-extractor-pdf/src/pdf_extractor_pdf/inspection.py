from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import fitz

from pdf_extractor_pdf.artifacts import artifact_hash, read_json, write_json
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.models import source_sha256
from pdf_extractor_pdf.workflow import require_phase, update_phase


def inspect_inventory(job: Job) -> dict[str, Any]:
    require_phase(job.evidence_dir, "inventory_frozen", "inspected")
    inventory = read_json(job.inventory)
    dpi = int(job.evidence.get("table_dpi", 220))
    root = job.evidence_dir / "segments"
    manifest_path = root / "manifest.json"
    inventory_hash = artifact_hash(job.inventory)
    existing = read_json(manifest_path) if manifest_path.is_file() else {}
    if existing:
        if existing.get("inventory_sha256") == inventory_hash and existing.get("dpi") == dpi and _valid_cache(existing):
            existing["cache_hit"] = True
            update_phase(job.evidence_dir, "inspected", "segment_evidence_generated", {"cache_hit": True})
            return existing
    old = {(item.get("table_id"), item.get("segment_id")): item for item in existing.get("segments", [])}
    source_hash = source_sha256(job.source)
    document = fitz.open(job.source)
    records = []
    reused = 0
    rendered = 0
    current_keys = set()
    for table in inventory["tables"]:
        table_dir = root / table["id"]
        table_dir.mkdir(parents=True, exist_ok=True)
        for segment in table["segments"]:
            key = (table["id"], segment["id"])
            current_keys.add(key)
            fingerprint = _fingerprint(source_hash, table["id"], segment, dpi)
            prior = old.get(key)
            if prior and prior.get("fingerprint") == fingerprint and _valid_record(prior):
                records.append(prior)
                reused += 1
                continue
            page = document[segment["page"] - 1]
            clip = fitz.Rect(*segment["bbox"])
            stem = f"{segment['id']}-{fingerprint[:12]}-page-{segment['page']:04d}"
            image_path = table_dir / f"{stem}.png"
            page.get_pixmap(dpi=dpi, alpha=False, clip=clip).save(image_path)
            geometry_path = table_dir / f"{stem}.json"
            geometry = {
                "table_id": table["id"],
                "segment_id": segment["id"],
                "page": segment["page"],
                "page_rect": list(page.rect),
                "rotation": page.rotation,
                "bbox": list(clip),
                "words": [list(word) for word in page.get_text("words", clip=clip)],
                "lines": _drawing_lines(page, clip),
            }
            write_json(geometry_path, geometry)
            records.append({
                "table_id": table["id"], "segment_id": segment["id"], "page": segment["page"],
                "fingerprint": fingerprint,
                "image": str(image_path), "image_sha256": artifact_hash(image_path),
                "geometry": str(geometry_path), "geometry_sha256": artifact_hash(geometry_path),
            })
            rendered += 1
    document.close()
    manifest = {
        "spec": "pdf-extractor-pdf/segment-evidence@1.0",
        "inventory_sha256": inventory_hash,
        "dpi": dpi,
        "cache_hit": False,
        "reused_segments": reused,
        "rendered_segments": rendered,
        "stale_segments": [list(key) for key in sorted(set(old) - current_keys)],
        "segments": records,
    }
    path = write_json(root / "manifest.json", manifest)
    update_phase(job.evidence_dir, "inspected", "segment_evidence_generated", {"manifest_sha256": artifact_hash(path)})
    return manifest


def _valid_cache(manifest: dict) -> bool:
    return all(_valid_record(item) for item in manifest.get("segments", []))


def _valid_record(item: dict) -> bool:
    image, geometry = Path(item["image"]), Path(item["geometry"])
    return (
        image.is_file() and artifact_hash(image) == item.get("image_sha256")
        and geometry.is_file() and artifact_hash(geometry) == item.get("geometry_sha256")
    )


def _fingerprint(source_hash: str, table_id: str, segment: dict, dpi: int) -> str:
    value = {
        "source_sha256": source_hash, "table_id": table_id,
        "segment_id": segment["id"], "page": segment["page"],
        "bbox": segment["bbox"], "rotation": segment.get("rotation", 0), "dpi": dpi,
    }
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _drawing_lines(page: fitz.Page, clip: fitz.Rect) -> list[dict]:
    lines = []
    for drawing in page.get_drawings():
        for item in drawing.get("items", []):
            if item[0] == "l":
                start, end = item[1], item[2]
                if clip.intersects(fitz.Rect(start, end)):
                    lines.append({"from": [start.x, start.y], "to": [end.x, end.y]})
            elif item[0] == "re" and clip.intersects(item[1]):
                lines.append({"rect": list(item[1])})
    return lines
