from __future__ import annotations

from pdf_extractor_pdf.cell_diff import blocking_diffs, cell_diffs, validate_modes
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.models import source_sha256


def validate_result(job: Job, result: dict, inventory: dict, reference: dict, evidence: list[dict]) -> tuple[list[dict], list[dict]]:
    issues, formatting = [], []
    if result.get("source_sha256") != source_sha256(job.source):
        issues.append(_issue("source_hash", "extraction_agent", "Result source hash does not match the PDF."))
    actual = {item.get("id"): item for item in result.get("tables", [])}
    inventories = {item["id"]: item for item in inventory["tables"]}
    references = {item["id"]: item for item in reference["tables"]}
    if set(actual) != set(inventories):
        issues.append(_issue("inventory_coverage", "extraction_agent", "Result table IDs do not match Inventory."))
    for table_id in sorted(set(inventories) & set(actual) & set(references)):
        found, display = _validate_table(actual[table_id], inventories[table_id], references[table_id], evidence)
        issues.extend(found)
        formatting.extend(display)
    return issues, formatting


def _validate_table(actual: dict, inventory: dict, expected: dict, evidence: list[dict]) -> tuple[list[dict], list[dict]]:
    issues, formatting = [], []
    rows, column_count, table_id = actual.get("rows", []), actual.get("column_count"), actual["id"]
    expected_count = expected["column_count"]
    modes = validate_modes(expected.get("comparison_modes"), expected_count)
    all_evidence = _evidence_refs(evidence, {table_id})
    if column_count != expected_count:
        issues.append(_issue(
            "column_count_mismatch", "extraction_agent", f"{table_id}: positional column count differs.",
            table_id=table_id, extractor_column_count=column_count,
            qa_column_count=expected_count, evidence_refs=all_evidence,
        ))
    if len(rows) != expected["row_count"]:
        issues.append(_issue(
            "row_count_mismatch", "main_agent", f"{table_id}: row count differs.", table_id=table_id,
            extractor_row_count=len(rows), qa_row_count=expected["row_count"], evidence_refs=all_evidence,
        ))
    provenance = actual.get("provenance")
    for sample in expected["samples"]:
        index, qa_row = sample["row_index"], sample["values"]
        extractor_row = rows[index] if index < len(rows) else None
        diffs = cell_diffs(extractor_row or [], qa_row, modes)
        blocking = blocking_diffs(diffs)
        sample_evidence = _sample_evidence(evidence, table_id, provenance, index) or all_evidence
        if extractor_row is None or blocking:
            issues.append(_issue(
                "sample_mismatch", "main_agent", f"{table_id}: QA sample row {index} differs.",
                table_id=table_id, row_index=index, sample_reasons=sample.get("reasons", []),
                extractor_sample=extractor_row, qa_reference=qa_row,
                cell_diffs=blocking, evidence_refs=sample_evidence,
            ))
        display = [item for item in diffs if item["content_equal"]]
        if display:
            formatting.append({
                "id": f"{table_id}:format:{index}", "classification": "format_only",
                "table_id": table_id, "row_index": index, "cell_diffs": display,
                "evidence_refs": sample_evidence,
            })
    segments = {item["id"]: item for item in inventory["segments"]}
    if not isinstance(provenance, list) or len(provenance) != len(rows):
        issues.append(_issue("provenance_alignment", "extraction_agent", f"{table_id}: provenance does not align.", table_id=table_id))
    else:
        for index, item in enumerate(provenance):
            segment = segments.get(item.get("segment_id"))
            if not segment or item.get("page") != segment["page"] or not _bbox_inside(item.get("bbox"), segment["bbox"]):
                issues.append(_issue("invalid_provenance", "extraction_agent", f"{table_id}: invalid provenance row {index}.", table_id=table_id, row_index=index))
                break
    return issues, formatting


def _evidence_refs(evidence: list[dict], ids: set[str]) -> list[str]:
    return [f"{item['table_id']}::{item['segment_id']}" for item in evidence if item["table_id"] in ids]


def _sample_evidence(evidence: list[dict], table_id: str, provenance: object, index: int) -> list[str]:
    if not isinstance(provenance, list) or index >= len(provenance):
        return []
    segment_id = provenance[index].get("segment_id")
    return _evidence_refs([x for x in evidence if x["segment_id"] == segment_id], {table_id})


def _bbox_inside(value: object, parent: list) -> bool:
    return isinstance(value, list) and len(value) == 4 and value[0] >= parent[0] and value[1] >= parent[1] and value[2] <= parent[2] and value[3] <= parent[3]


def _issue(code: str, route: str, message: str, **details) -> dict:
    identity = ":".join(str(x) for x in [details.get("table_id", "global"), code, details.get("row_index", "")])
    return {"id": identity, "code": code, "route": route, "message": message, **details}
