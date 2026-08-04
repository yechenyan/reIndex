from __future__ import annotations

from pathlib import Path

from pdf_extractor_pdf.artifacts import artifact_hash, preserve_input, read_json, write_json
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.workflow import require_phase, update_phase


def resolve_merges(job: Job, draft_path: Path) -> dict:
    require_phase(job.evidence_dir, "reviewed", "complete")
    review_path = job.evidence_dir / "review.json"
    review = read_json(review_path)
    draft = read_json(draft_path)
    if draft.get("spec") != "pdf-extractor-pdf/merge-decisions-draft@1.0" or draft.get("role") != "main_agent":
        raise ValueError("merge decisions must be a main_agent draft")
    if draft.get("inventory_sha256") != artifact_hash(job.inventory):
        raise ValueError("merge decisions inventory hash mismatch")
    candidates = {(item["left"], item["right"]) for item in review.get("merge_candidates", [])}
    decisions = draft.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        raise ValueError("at least one merge decision is required")
    seen = set()
    evidence = _segment_evidence(job)
    for item in decisions:
        pair = (item.get("left"), item.get("right"))
        if pair not in candidates or pair in seen:
            raise ValueError(f"decision does not match a unique review candidate: {pair}")
        if item.get("decision") != "keep_separate" or not str(item.get("reason", "")).strip():
            raise ValueError("only reasoned keep_separate decisions can be frozen; merges require reopen-inventory")
        pages = item.get("evidence_pages")
        if not isinstance(pages, list) or not pages:
            raise ValueError("merge decision requires evidence_pages")
        table_pages = _table_pages(job, pair)
        if not set(pages).issubset(table_pages):
            raise ValueError("merge decision evidence page is outside the candidate tables")
        item["evidence"] = [value for value in evidence if value["page"] in pages]
        if not item["evidence"]:
            raise ValueError("merge decision has no frozen Segment evidence")
        seen.add(pair)
    frozen = {
        **draft,
        "spec": "pdf-extractor-pdf/merge-decisions@1.0",
        "review_sha256": artifact_hash(review_path),
        "draft_sha256": artifact_hash(draft_path),
        "frozen": True,
    }
    target = job.evidence_dir / "merge-decisions.json"
    write_json(target, frozen)
    preserved = preserve_input(draft_path, job.evidence_dir, "merge-decisions-draft")
    (job.evidence_dir / "final.json").unlink(missing_ok=True)
    update_phase(job.evidence_dir, "reference_frozen", "merge_decisions_frozen", {"agent_output": str(preserved)})
    return frozen


def _segment_evidence(job: Job) -> list[dict]:
    manifest = read_json(job.evidence_dir / "segments" / "manifest.json")
    return [{
        "table_id": item["table_id"], "segment_id": item["segment_id"], "page": item["page"],
        "image_sha256": item["image_sha256"], "geometry_sha256": item["geometry_sha256"],
    } for item in manifest["segments"]]


def _table_pages(job: Job, pair: tuple[str, str]) -> set[int]:
    inventory = read_json(job.inventory)
    return {
        segment["page"] for table in inventory["tables"] if table["id"] in pair
        for segment in table["segments"]
    }
