from __future__ import annotations

from pathlib import Path

from pdf_extractor_pdf.artifacts import artifact_hash, preserve_input, read_json, write_json
from pdf_extractor_pdf.cell_diff import validate_modes
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.line_wrap import apply_table_decisions, validate_decisions, write_decision_artifact
from pdf_extractor_pdf.models import source_sha256
from pdf_extractor_pdf.repair_scope import merge_reference_patch
from pdf_extractor_pdf.workflow import require_phase, update_phase


def required_sample_indices(row_count: int, segment_row_counts: list[int]) -> list[int]:
    if row_count < 0 or any(value < 0 for value in segment_row_counts):
        raise ValueError("row counts cannot be negative")
    if sum(segment_row_counts) != row_count:
        raise ValueError("segment row counts must sum to table row count")
    indices = set(range(min(3, row_count)))
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
    if draft.get("spec") != "pdf-extractor-pdf/reference-draft@2.0":
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
        inventory_table = next(x for x in inventory["tables"] if x["id"] == table["id"])
        _validate_table(table, inventory_table)
    tables = [apply_table_decisions(table, table.get("line_wrap_decisions", [])) for table in tables]
    frozen = {
        **draft, "tables": tables, "spec": "pdf-extractor-pdf/reference@2.0",
        "frozen": True, "draft_sha256": artifact_hash(draft_path),
    }
    write_json(job.reference, frozen)
    write_decision_artifact(job, tables)
    preserved = preserve_input(draft_path, job.evidence_dir, "reference-draft")
    update_phase(job.evidence_dir, "reference_frozen", "reference_frozen", {
        "reference_sha256": artifact_hash(job.reference), "agent_output": str(preserved),
    })
    return frozen


def reopen_reference(job: Job, reason: str) -> dict:
    require_phase(job.evidence_dir, "reference_frozen", "reviewed", "complete")
    for path in [job.reference, job.evidence_dir / "normalization-decisions.json", job.evidence_dir / "review.json", job.evidence_dir / "review.html", job.evidence_dir / "final.json"]:
        path.unlink(missing_ok=True)
    update_phase(job.evidence_dir, "inspected", "reference_reopened", {"reason": reason})
    return {"phase": "inspected", "reason": reason}


def _validate_table(table: dict, inventory_table: dict) -> None:
    column_count = table.get("column_count")
    row_count = table.get("row_count")
    segment_rows = table.get("segment_row_counts")
    source_rows = table.get("segment_source_row_counts")
    repeated = table.get("segment_repeated_leading_rows")
    if not isinstance(column_count, int) or isinstance(column_count, bool) or column_count < 1:
        raise ValueError("reference column_count must be a positive integer")
    if column_count != inventory_table["column_count"]:
        raise ValueError("reference column_count must match frozen Inventory")
    table["comparison_modes"] = validate_modes(table.get("comparison_modes"), column_count)
    if (
        not isinstance(row_count, int) or not isinstance(segment_rows, list)
        or len(segment_rows) != len(inventory_table["segments"])
    ):
        raise ValueError("reference row counts are invalid")
    if (
        not isinstance(source_rows, list) or not isinstance(repeated, list)
        or len(source_rows) != len(segment_rows) or len(repeated) != len(segment_rows)
        or repeated[0] != 0
        or any(not isinstance(x, int) or isinstance(x, bool) or x < 0 for x in source_rows + repeated)
        or any(drop > count for drop, count in zip(repeated, source_rows))
        or segment_rows != [count - drop for count, drop in zip(source_rows, repeated)]
    ):
        raise ValueError("reference repeated leading-row accounting is invalid")
    validate_decisions(table.get("line_wrap_decisions", []), table.get("id", "unknown"))
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
        if not isinstance(values, list) or len(values) != column_count or any(not isinstance(value, str) for value in values):
            raise ValueError("reference sample values must match column_count and be strings")
        declared = sample.get("source_blank_indices", [])
        if not isinstance(declared, list) or len(set(declared)) != len(declared) or any(
            not isinstance(value, int) or value < 0 or value >= column_count for value in declared
        ):
            raise ValueError("source_blank_indices must contain unique valid column indices")
        actual_blanks = {position for position, value in enumerate(values) if not value.strip()}
        if actual_blanks != set(declared):
            raise ValueError("every empty QA sample cell must be explicitly declared source blank")
        sample["source_blank_indices"] = sorted(declared)
