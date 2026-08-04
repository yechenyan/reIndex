from __future__ import annotations

from pathlib import Path

from pdf_extractor_pdf.artifacts import artifact_hash, preserve_input, read_json, write_json
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.models import source_sha256
from pdf_extractor_pdf.reference import required_sample_indices
from pdf_extractor_pdf.repair_scope import selected_table_ids
from pdf_extractor_pdf.workflow import require_phase


def scaffold_reference(job: Job) -> dict:
    require_phase(job.evidence_dir, "inspected")
    inventory = read_json(job.inventory)
    selected = selected_table_ids(job, {item["id"] for item in inventory["tables"]})
    evidence = _evidence_by_segment(job)
    value = _base(job, "pdf-extractor-pdf/reference-structure-template@1.0")
    value["instructions"] = "QA fills columns and each Segment row_count from source evidence only."
    value["tables"] = [
        {
            "id": table["id"], "title": table.get("title", ""), "columns": [],
            "segments": [
                {
                    "id": segment["id"], "page": segment["page"], "row_count": None,
                    "image": evidence[(table["id"], segment["id"])]["image"],
                }
                for segment in table["segments"]
            ],
        }
        for table in inventory["tables"] if table["id"] in selected
    ]
    path = job.evidence_dir / "reference-work" / "structure-template.json"
    write_json(path, value)
    return {"path": str(path), "tables": len(value["tables"])}


def plan_reference(job: Job, draft_path: Path) -> dict:
    require_phase(job.evidence_dir, "inspected")
    inventory, draft = read_json(job.inventory), read_json(draft_path)
    _validate_identity(job, draft)
    selected = selected_table_ids(job, {item["id"] for item in inventory["tables"]})
    expected = {item["id"]: item for item in inventory["tables"] if item["id"] in selected}
    supplied = {item.get("id"): item for item in draft.get("tables", [])}
    if set(supplied) != set(expected):
        raise ValueError("reference structure must cover exactly the current repair scope")
    tables = []
    for table_id, inventory_table in expected.items():
        item = supplied[table_id]
        columns = item.get("columns")
        if not isinstance(columns, list) or not columns or any(not isinstance(x, str) or not x for x in columns):
            raise ValueError(f"{table_id}: columns must be non-empty strings")
        segments = item.get("segments", [])
        expected_ids = [x["id"] for x in inventory_table["segments"]]
        if [x.get("id") for x in segments] != expected_ids:
            raise ValueError(f"{table_id}: Segment order or coverage differs from Inventory")
        counts = [x.get("row_count") for x in segments]
        if any(not isinstance(x, int) or x < 0 for x in counts):
            raise ValueError(f"{table_id}: Segment row counts must be non-negative integers")
        total = sum(counts)
        indices = required_sample_indices(total, counts)
        tables.append({
            "id": table_id, "columns": columns, "row_count": total,
            "segment_row_counts": counts,
            "samples": [
                {"row_index": index, "reasons": _sample_reasons(index, total, counts), "values": [None] * len(columns)}
                for index in indices
            ],
        })
    value = _base(job, "pdf-extractor-pdf/reference-draft@1.0")
    value["tables"] = tables
    path = job.evidence_dir / "reference-work" / "reference-template.json"
    write_json(path, value)
    preserved = preserve_input(draft_path, job.evidence_dir, "reference-structure-draft")
    return {"path": str(path), "structure_draft": str(preserved), "tables": len(tables)}


def _base(job: Job, spec: str) -> dict:
    return {
        "spec": spec, "role": "qa_agent", "independent_from_extractor": True,
        "source_evidence_only": True, "source_sha256": source_sha256(job.source),
        "inventory_sha256": artifact_hash(job.inventory),
    }


def _validate_identity(job: Job, value: dict) -> None:
    if value.get("spec") != "pdf-extractor-pdf/reference-structure-draft@1.0":
        raise ValueError("reference structure draft spec mismatch")
    identity = _base(job, value["spec"])
    for key in ["role", "independent_from_extractor", "source_evidence_only", "source_sha256", "inventory_sha256"]:
        if value.get(key) != identity[key]:
            raise ValueError(f"reference structure has invalid {key}")


def _evidence_by_segment(job: Job) -> dict:
    manifest = read_json(job.evidence_dir / "segments" / "manifest.json")
    return {(item["table_id"], item["segment_id"]): item for item in manifest["segments"]}


def _sample_reasons(index: int, total: int, counts: list[int]) -> list[str]:
    reasons = []
    if index < min(2, total):
        reasons.append("first_rows")
    if index >= max(0, total - 2):
        reasons.append("last_rows")
    if total and index == total // 2:
        reasons.append("middle_row")
    boundary = 0
    for count in counts[:-1]:
        boundary += count
        if index == boundary - 1:
            reasons.append("segment_boundary_before")
        if index == boundary:
            reasons.append("segment_boundary_after")
    return reasons
