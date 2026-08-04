from __future__ import annotations

from pathlib import Path

from pdf_extractor_pdf.artifacts import artifact_hash, preserve_input, read_json, write_json
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.models import source_sha256
from pdf_extractor_pdf.repair_scope import merge_reference_patch
from pdf_extractor_pdf.workflow import require_phase, update_phase


def required_sample_indices(row_count: int, segment_row_counts: list[int]) -> list[int]:
    if row_count < 0 or any(value < 0 for value in segment_row_counts):
        raise ValueError("row counts cannot be negative")
    if sum(segment_row_counts) != row_count:
        raise ValueError("segment row counts must sum to table row count")
    indices = set(range(min(2, row_count)))
    indices.update(range(max(0, row_count - 2), row_count))
    if row_count:
        indices.add(row_count // 2)
    boundary = 0
    for count in segment_row_counts[:-1]:
        boundary += count
        if boundary:
            indices.add(boundary - 1)
        if boundary < row_count:
            indices.add(boundary)
    return sorted(indices)


def freeze_reference(job: Job, draft_path: Path) -> dict:
    require_phase(job.evidence_dir, "inspected")
    inventory = read_json(job.inventory)
    draft = read_json(draft_path)
    if draft.get("spec") != "pdf-extractor-pdf/reference-draft@1.0":
        raise ValueError("reference draft spec mismatch")
    if draft.get("role") != "qa_agent" or not draft.get("independent_from_extractor") or not draft.get("source_evidence_only"):
        raise ValueError("reference must be independently transcribed by the QA agent from source evidence")
    if draft.get("source_sha256") != source_sha256(job.source):
        raise ValueError("reference source hash mismatch")
    if draft.get("inventory_sha256") != artifact_hash(job.inventory):
        raise ValueError("reference inventory hash mismatch")
    tables = draft.get("tables")
    if not isinstance(tables, list):
        raise ValueError("reference tables must be a list")
    by_id = {item.get("id"): item for item in tables}
    tables = merge_reference_patch(job, by_id)
    by_id = {item.get("id"): item for item in tables}
    if set(by_id) != {item["id"] for item in inventory["tables"]}:
        raise ValueError("reference must cover the complete frozen inventory")
    for table in tables:
        _validate_table(table, len(next(x for x in inventory["tables"] if x["id"] == table["id"])["segments"]))
    frozen = {
        **draft, "tables": tables, "spec": "pdf-extractor-pdf/reference@1.0",
        "frozen": True, "draft_sha256": artifact_hash(draft_path),
    }
    write_json(job.reference, frozen)
    preserved = preserve_input(draft_path, job.evidence_dir, "reference-draft")
    update_phase(job.evidence_dir, "reference_frozen", "reference_frozen", {
        "reference_sha256": artifact_hash(job.reference), "agent_output": str(preserved),
    })
    return frozen


def reopen_reference(job: Job, reason: str) -> dict:
    require_phase(job.evidence_dir, "reference_frozen", "reviewed", "complete")
    for path in [job.reference, job.evidence_dir / "review.json", job.evidence_dir / "review.html", job.evidence_dir / "final.json"]:
        path.unlink(missing_ok=True)
    update_phase(job.evidence_dir, "inspected", "reference_reopened", {"reason": reason})
    return {"phase": "inspected", "reason": reason}


def _validate_table(table: dict, segment_count: int) -> None:
    columns = table.get("columns")
    row_count = table.get("row_count")
    segment_rows = table.get("segment_row_counts")
    if not isinstance(columns, list) or not columns or any(not isinstance(value, str) for value in columns):
        raise ValueError("reference columns must be non-empty strings")
    if not isinstance(row_count, int) or not isinstance(segment_rows, list) or len(segment_rows) != segment_count:
        raise ValueError("reference row counts are invalid")
    required = required_sample_indices(row_count, segment_rows)
    samples = table.get("samples")
    if not isinstance(samples, list):
        raise ValueError("reference samples must be a list")
    by_index = {sample.get("row_index"): sample for sample in samples}
    if not set(required).issubset(by_index):
        raise ValueError(f"reference is missing required sample rows: {sorted(set(required) - set(by_index))}")
    for index, sample in by_index.items():
        values = sample.get("values")
        if not isinstance(index, int) or index < 0 or index >= row_count:
            raise ValueError("reference sample index outside table")
        if not isinstance(values, list) or len(values) != len(columns) or any(not isinstance(value, str) for value in values):
            raise ValueError("reference sample values must match columns and be strings")
