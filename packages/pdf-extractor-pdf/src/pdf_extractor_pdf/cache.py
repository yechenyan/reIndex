from __future__ import annotations

import fitz
from pathlib import Path

from pdf_extractor_pdf.artifacts import artifact_hash, read_json
from pdf_extractor_pdf.inspection import _valid_cache
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.models import source_sha256
from pdf_extractor_pdf.workflow import load_state


def verify_cache(job: Job) -> dict:
    """Verify neutral evidence caches without changing workflow state."""
    state = load_state(job.evidence_dir)
    prepare_path = job.evidence_dir / "prepare-manifest.json"
    segment_path = job.evidence_dir / "segments" / "manifest.json"
    prepare_ok = _verify_prepare(job, prepare_path)
    audit_ok = _verify_inventory_audit(job)
    inspect_ok = False
    if segment_path.is_file() and job.inventory.is_file():
        manifest = read_json(segment_path)
        inspect_ok = (
            manifest.get("inventory_sha256") == artifact_hash(job.inventory)
            and manifest.get("dpi") == int(job.evidence.get("table_dpi", 220))
            and _valid_cache(manifest)
        )
    return {
        "spec": "pdf-extractor-pdf/cache-verification@1.0",
        "phase": state["phase"],
        "prepare_cache_hit": prepare_ok,
        "inventory_audit_hit": audit_ok,
        "inspect_cache_hit": inspect_ok,
        "ok": prepare_ok and audit_ok and inspect_ok,
    }


def _verify_prepare(job: Job, path) -> bool:
    if not path.is_file():
        return False
    manifest = read_json(path)
    document = fitz.open(job.source)
    page_count = len(document)
    document.close()
    if manifest.get("source_sha256") != source_sha256(job.source) or manifest.get("page_count") != page_count:
        return False
    pages = job.evidence_dir / "pages-low"
    for number in range(1, page_count + 1):
        page = pages / f"page-{number:04d}.png"
        if not page.is_file() or manifest.get("page_hashes", {}).get(page.name) != artifact_hash(page):
            return False
    for value in manifest.get("contacts", []):
        contact = Path(value)
        if not contact.is_file() or manifest.get("contact_hashes", {}).get(contact.name) != artifact_hash(contact):
            return False
    return bool(manifest.get("contacts"))


def _verify_inventory_audit(job: Job) -> bool:
    path = job.evidence_dir / "inventory-audit.json"
    if not path.is_file() or not job.inventory.is_file():
        return False
    report, inventory = read_json(path), read_json(job.inventory)
    if not report.get("passed") or report.get("draft_sha256") != inventory.get("draft_sha256"):
        return False
    for item in report.get("segments", []):
        overlay = Path(item["overlay"])
        if not overlay.is_file() or artifact_hash(overlay) != item.get("overlay_sha256"):
            return False
    return bool(report.get("segments"))
