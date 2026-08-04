from __future__ import annotations

from math import ceil
from pathlib import Path
from typing import Iterable

import fitz
from PIL import Image, ImageDraw, ImageOps

from pdf_extractor_pdf.artifacts import artifact_hash, write_json
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.models import source_sha256
from pdf_extractor_pdf.workflow import require_phase, update_phase


def prepare(job: Job) -> dict:
    require_phase(job.evidence_dir, "initialized", "prepared")
    dpi = int(job.evidence.get("thumbnail_dpi", 72))
    document = fitz.open(job.source)
    signature = {
        "source_sha256": source_sha256(job.source), "page_count": len(document), "dpi": dpi,
        "contact_pages": int(job.evidence.get("contact_pages", 8)),
        "contact_columns": int(job.evidence.get("contact_columns", 4)),
        "contact_overlap_pages": int(job.evidence.get("contact_overlap_pages", 1)),
    }
    manifest_path = job.evidence_dir / "prepare-manifest.json"
    pages_dir = job.evidence_dir / "pages-low"
    existing = _load_optional(manifest_path)
    expected = [pages_dir / f"page-{number:04d}.png" for number in range(1, len(document) + 1)]
    cache_hit = existing and all(existing.get(key) == value for key, value in signature.items())
    page_hashes = existing.get("page_hashes", {}) if existing else {}
    cache_hit = bool(cache_hit and all(
        path.is_file() and page_hashes.get(path.name) == artifact_hash(path) for path in expected
    ))
    contact_paths = [Path(path) for path in existing.get("contacts", [])] if existing else []
    contact_hashes = existing.get("contact_hashes", {}) if existing else {}
    cache_hit = bool(cache_hit and contact_paths and all(
        path.is_file() and contact_hashes.get(path.name) == artifact_hash(path) for path in contact_paths
    ))
    if cache_hit:
        document.close()
        manifest = {**existing, "cache_hit": True}
        write_json(manifest_path, manifest)
        update_phase(job.evidence_dir, "prepared", "evidence_prepared", {"cache_hit": True})
        return manifest
    page_info = []
    if not cache_hit:
        pages_dir.mkdir(parents=True, exist_ok=True)
        for number, page in enumerate(document, 1):
            pixmap = page.get_pixmap(dpi=dpi, alpha=False)
            pixmap.save(expected[number - 1])
    for number, page in enumerate(document, 1):
        text = page.get_text("text")
        page_info.append({
            "page": number,
            "width": round(page.rect.width, 3),
            "height": round(page.rect.height, 3),
            "rotation": page.rotation,
            "text_chars": len(text),
            "word_count": len(page.get_text("words")),
        })
    document.close()
    contacts, windows = _contacts(expected, job.evidence_dir / "contact-sheets", job)
    manifest = {
        **signature, "cache_hit": False, "pages": page_info, "contacts": contacts,
        "contact_windows": windows,
        "page_hashes": {path.name: artifact_hash(path) for path in expected},
        "contact_hashes": {Path(path).name: artifact_hash(Path(path)) for path in contacts},
    }
    write_json(manifest_path, manifest)
    update_phase(job.evidence_dir, "prepared", "evidence_prepared", {"cache_hit": cache_hit})
    return manifest


def render_pages(job: Job, pages: Iterable[int], dpi: int | None = None) -> list[str]:
    require_phase(job.evidence_dir, "prepared", "inventory_frozen", "inspected", "reference_frozen", "reviewed")
    document = fitz.open(job.source)
    dpi = dpi or int(job.evidence.get("table_dpi", 220))
    target = job.evidence_dir / "pages-high"
    target.mkdir(parents=True, exist_ok=True)
    written = []
    for number in sorted(set(pages)):
        if number < 1 or number > len(document):
            raise ValueError(f"page outside document: {number}")
        path = target / f"page-{number:04d}-{dpi}dpi.png"
        document[number - 1].get_pixmap(dpi=dpi, alpha=False).save(path)
        written.append(str(path))
    document.close()
    return written


def _contacts(pages: list[Path], target: Path, job: Job) -> tuple[list[str], list[dict]]:
    target.mkdir(parents=True, exist_ok=True)
    per_sheet = int(job.evidence.get("contact_pages", 8))
    columns = int(job.evidence.get("contact_columns", 4))
    overlap = int(job.evidence.get("contact_overlap_pages", 1))
    if per_sheet < 2 or overlap < 0 or overlap >= per_sheet:
        raise ValueError("contact overlap must be non-negative and smaller than contact_pages")
    written, windows = [], []
    step = per_sheet - overlap
    for sheet_number, offset in enumerate(range(0, len(pages), step), 1):
        batch = pages[offset:offset + per_sheet]
        if not batch:
            break
        images = [Image.open(path).convert("RGB") for path in batch]
        thumbs = []
        for number, image in enumerate(images, offset + 1):
            image.thumbnail((300, 420))
            frame = ImageOps.expand(image, border=(2, 26, 2, 2), fill="white")
            ImageDraw.Draw(frame).text((8, 5), f"Page {number}", fill="black")
            thumbs.append(frame)
        cell_w, cell_h = max(x.width for x in thumbs), max(x.height for x in thumbs)
        sheet = Image.new("RGB", (columns * cell_w, ceil(len(thumbs) / columns) * cell_h), "white")
        for local, image in enumerate(thumbs):
            sheet.paste(image, ((local % columns) * cell_w, (local // columns) * cell_h))
        path = target / f"contact-{sheet_number:03d}.jpg"
        sheet.save(path, quality=88)
        written.append(str(path))
        windows.append({"path": str(path), "pages": list(range(offset + 1, offset + len(batch) + 1))})
        for image in images:
            image.close()
        if offset + len(batch) == len(pages):
            break
    return written, windows


def _load_optional(path: Path) -> dict:
    if not path.is_file():
        return {}
    import json
    return json.loads(path.read_text(encoding="utf-8"))
