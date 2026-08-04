from __future__ import annotations

from pathlib import Path

from pdf_extractor_pdf.artifacts import artifact_hash, preserve_input, read_json, write_json
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.line_wrap import candidates_for_job, validate_decisions
from pdf_extractor_pdf.models import source_sha256
from pdf_extractor_pdf.reference import required_sample_indices
from pdf_extractor_pdf.repair_scope import active_scope, selected_table_ids
from pdf_extractor_pdf.workflow import require_phase


def scaffold_reference(job: Job) -> dict:
    require_phase(job.evidence_dir, "inspected")
    inventory = read_json(job.inventory)
    selected = selected_table_ids(job, {item["id"] for item in inventory["tables"]})
    evidence = _evidence_by_segment(job)
    wrap_candidates = candidates_for_job(job, selected)
    _reuse_wrap_decisions(job, wrap_candidates)
    value = _base(job, "pdf-extractor-pdf/reference-structure-template@2.0")
    value["instructions"] = (
        "QA confirms frozen positional column_count, fills one exact/text mode per column, "
        "and counts retained rows from source evidence. Row 0 is not implicitly a header."
    )
    value["tables"] = [
        {
            "id": table["id"], "title": table.get("title", ""),
            "column_count": table["column_count"], "comparison_modes": [],
            "line_wrap_candidates": wrap_candidates.get(table["id"], []),
            "segments": [
                {
                    "id": segment["id"], "page": segment["page"], "source_row_count": None,
                    "repeated_leading_rows": 0 if index == 0 else None,
                    "image": evidence[(table["id"], segment["id"])]["image"],
                }
                for index, segment in enumerate(table["segments"])
            ],
        }
        for table in inventory["tables"] if table["id"] in selected
    ]
    path = job.evidence_dir / "reference-work" / "structure-template.json"
    write_json(path, value)
    return {
        "path": str(path), "tables": len(value["tables"]),
        "line_wrap_candidates": sum(len(x["line_wrap_candidates"]) for x in value["tables"]),
    }


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
        column_count = item.get("column_count")
        if (
            not isinstance(column_count, int) or isinstance(column_count, bool)
            or column_count != inventory_table["column_count"]
        ):
            raise ValueError(f"{table_id}: column_count must match frozen Inventory")
        modes = item.get("comparison_modes")
        if not isinstance(modes, list) or len(modes) != column_count or any(x not in {"exact", "text"} for x in modes):
            raise ValueError(f"{table_id}: comparison_modes must contain one exact/text value per column")
        segments = item.get("segments", [])
        expected_ids = [x["id"] for x in inventory_table["segments"]]
        if [x.get("id") for x in segments] != expected_ids:
            raise ValueError(f"{table_id}: Segment order or coverage differs from Inventory")
        source_counts = [x.get("source_row_count") for x in segments]
        repeated = [x.get("repeated_leading_rows") for x in segments]
        if any(not isinstance(x, int) or isinstance(x, bool) or x < 0 for x in source_counts):
            raise ValueError(f"{table_id}: source_row_count must be a non-negative integer per Segment")
        if any(not isinstance(x, int) or isinstance(x, bool) or x < 0 for x in repeated):
            raise ValueError(f"{table_id}: repeated_leading_rows must be a non-negative integer per Segment")
        if repeated[0] != 0 or any(drop > count for drop, count in zip(repeated, source_counts)):
            raise ValueError(f"{table_id}: repeated leading-row counts are invalid")
        counts = [count - drop for count, drop in zip(source_counts, repeated)]
        total = sum(counts)
        indices = required_sample_indices(total, counts)
        wrap_decisions = validate_decisions(item.get("line_wrap_candidates", []), table_id)
        tables.append({
            "id": table_id, "column_count": column_count,
            "comparison_modes": modes, "row_count": total,
            "segment_row_counts": counts, "segment_source_row_counts": source_counts,
            "segment_repeated_leading_rows": repeated,
            "line_wrap_decisions": wrap_decisions,
            "samples": [
                {
                    "row_index": index, "reasons": _sample_reasons(index, total, counts),
                    "values": [None] * column_count, "source_blank_indices": [],
                }
                for index in indices
            ],
        })
    value = _base(job, "pdf-extractor-pdf/reference-draft@2.0")
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
    if value.get("spec") != "pdf-extractor-pdf/reference-structure-draft@2.0":
        raise ValueError("reference structure draft spec mismatch")
    identity = _base(job, value["spec"])
    for key in ["role", "independent_from_extractor", "source_evidence_only", "source_sha256", "inventory_sha256"]:
        if value.get(key) != identity[key]:
            raise ValueError(f"reference structure has invalid {key}")


def _evidence_by_segment(job: Job) -> dict:
    manifest = read_json(job.evidence_dir / "segments" / "manifest.json")
    return {(item["table_id"], item["segment_id"]): item for item in manifest["segments"]}


def _reuse_wrap_decisions(job: Job, candidates: dict[str, list[dict]]) -> None:
    scope = active_scope(job)
    if not scope:
        return
    for table_id, table in scope["baseline"]["reference_tables"].items():
        prior = {item["id"]: item["decision"] for item in table.get("line_wrap_decisions", [])}
        for candidate in candidates.get(table_id, []):
            if candidate.get("decision") is None and candidate["id"] in prior:
                candidate["decision"] = prior[candidate["id"]]
                candidate["decision_source"] = "qa"


def _sample_reasons(index: int, total: int, counts: list[int]) -> list[str]:
    reasons = []
    if index < min(3, total):
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
