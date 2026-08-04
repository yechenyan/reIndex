from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz

from pdf_extractor_pdf.artifacts import artifact_hash, preserve_input, read_json, write_json
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.models import source_sha256
from pdf_extractor_pdf.workflow import require_phase, update_phase

LABELS = {"table", "no_table", "continuation", "uncertain"}


def freeze_inventory(job: Job, draft_path: Path) -> dict[str, Any]:
    require_phase(job.evidence_dir, "prepared")
    draft = read_json(draft_path)
    document = fitz.open(job.source)
    _validate_draft(draft, job, document)
    document.close()
    from pdf_extractor_pdf.inventory_audit import require_inventory_audit
    require_inventory_audit(job, draft_path)
    frozen = {
        **draft,
        "spec": "pdf-extractor-pdf/inventory@1.0",
        "source_sha256": source_sha256(job.source),
        "draft_sha256": artifact_hash(draft_path),
        "frozen": True,
    }
    write_json(job.inventory, frozen)
    preserved = preserve_input(draft_path, job.evidence_dir, "inventory-draft")
    update_phase(job.evidence_dir, "inventory_frozen", "inventory_frozen", {
        "inventory_sha256": artifact_hash(job.inventory),
        "table_count": len(frozen["tables"]),
        "segment_count": sum(len(table["segments"]) for table in frozen["tables"]),
        "agent_output": str(preserved),
    })
    return frozen


def reopen_inventory(job: Job, reason: str) -> dict:
    require_phase(job.evidence_dir, "inventory_frozen", "inspected", "reference_frozen", "reviewed", "complete")
    for path in [job.inventory, job.reference, job.evidence_dir / "merge-decisions.json", job.evidence_dir / "review.json", job.evidence_dir / "review.html", job.evidence_dir / "final.json"]:
        path.unlink(missing_ok=True)
    update_phase(job.evidence_dir, "prepared", "inventory_reopened", {"reason": reason})
    return {"phase": "prepared", "reason": reason}


def _validate_draft(draft: dict, job: Job, document: fitz.Document) -> None:
    if draft.get("spec") != "pdf-extractor-pdf/inventory-draft@1.0":
        raise ValueError("inventory draft spec mismatch")
    if draft.get("role") != "finder_agent" or not draft.get("reviewed_all_pages"):
        raise ValueError("finder_agent must review all pages")
    if draft.get("source_sha256") != source_sha256(job.source):
        raise ValueError("inventory source hash mismatch")
    findings = draft.get("page_findings")
    if not isinstance(findings, list):
        raise ValueError("page_findings must be a list")
    page_map = {item.get("page"): item for item in findings if isinstance(item, dict)}
    expected = set(range(1, len(document) + 1))
    if set(page_map) != expected or len(findings) != len(document):
        raise ValueError("page_findings must cover every page exactly once")
    if any(item.get("label") not in LABELS for item in findings):
        raise ValueError("invalid page finding label")
    uncertain = [item["page"] for item in findings if item["label"] == "uncertain"]
    if uncertain:
        raise ValueError(f"uncertain pages block inventory freeze: {uncertain}")
    tables = draft.get("tables")
    if not isinstance(tables, list):
        raise ValueError("tables must be a list")
    ids = [table.get("id") for table in tables]
    if None in ids or len(ids) != len(set(ids)):
        raise ValueError("logical table IDs must be non-empty and unique")
    segment_pages = []
    for table in tables:
        column_count = table.get("column_count")
        if not isinstance(column_count, int) or isinstance(column_count, bool) or column_count < 1:
            raise ValueError(f"table {table.get('id')} needs a positive column_count")
        segments = table.get("segments")
        if not isinstance(segments, list) or not segments:
            raise ValueError(f"table {table.get('id')} has no segments")
        segment_ids = [item.get("id") for item in segments]
        if None in segment_ids or len(segment_ids) != len(set(segment_ids)):
            raise ValueError(f"segment IDs must be unique within {table.get('id')}")
        for segment in segments:
            page = segment.get("page")
            if page not in expected:
                raise ValueError(f"segment page outside document: {page}")
            _validate_bbox(segment.get("bbox"), document[page - 1].rect)
            segment_pages.append(page)
    accepted_pages = {item["page"] for item in findings if item["label"] in {"table", "continuation"}}
    if accepted_pages != set(segment_pages):
        raise ValueError("table/continuation findings must exactly match segment pages")


def _validate_bbox(value: Any, rect: fitz.Rect) -> None:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("segment bbox must have four coordinates")
    bbox = fitz.Rect(*value)
    if bbox.is_empty or not rect.contains(bbox):
        raise ValueError(f"segment bbox outside page: {value}")
