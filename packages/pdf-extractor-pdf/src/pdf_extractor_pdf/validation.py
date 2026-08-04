from __future__ import annotations

import json

from pdf_extractor_pdf.artifacts import artifact_hash, read_json, write_json
from pdf_extractor_pdf.cell_diff import cell_diffs, normalized_values
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.merge_detection import merge_candidates
from pdf_extractor_pdf.models import source_sha256
from pdf_extractor_pdf.review_cases import build_review_cases
from pdf_extractor_pdf.repair_scope import scope_violations
from pdf_extractor_pdf.runner import _write_outputs, invoke_twice
from pdf_extractor_pdf.workflow import update_phase


def validate(job: Job) -> dict:
    first, second = invoke_twice(job)
    inventory, reference = read_json(job.inventory), read_json(job.reference)
    evidence = read_json(job.evidence_dir / "segments" / "manifest.json")["segments"]
    issues = []
    if _canonical(first) != _canonical(second):
        issues.append(_issue("nondeterministic_output", "extraction_agent", "Two extractor runs differ."))
    issues.extend(_validate_result(job, first, inventory, reference, evidence))
    issues.extend(scope_violations(job, first, inventory, reference))
    decisions = _merge_decisions(job)
    threshold = float(job.policy.get("merge_candidate_threshold", 0.85))
    candidates = merge_candidates(first, inventory, threshold, decisions)
    for item in candidates:
        item["evidence_refs"] = _evidence_refs(evidence, {item["left"], item["right"]})
    blocking = [item for item in candidates if item["confidence"] >= threshold and not item.get("resolved")]
    cases, repair_plan = build_review_cases(issues)
    _write_outputs(job, first)
    report = {
        "spec": "pdf-extractor-pdf/review@3.0", "review_target": "main_agent",
        "passed": not issues and not blocking, "deterministic": _canonical(first) == _canonical(second),
        "source_sha256": source_sha256(job.source), "inventory_sha256": artifact_hash(job.inventory),
        "reference_sha256": artifact_hash(job.reference), "extractor_sha256": artifact_hash(job.main),
        "summary": {
            "issue_count": len(issues), "case_count": len(cases),
            "deterministically_routed_cases": sum(x["route"] != "main_agent" for x in cases),
            "main_agent_case_reviews": sum(x["route"] == "main_agent" for x in cases),
            "merge_reviews": sum(not x.get("resolved") for x in candidates),
        },
        "issues": issues, "review_cases": cases, "repair_plan": repair_plan,
        "issue_groups": _group_ids(issues), "merge_candidates": candidates,
        "evidence_index": _evidence_index(evidence),
        "review_queue": _review_queue(cases, candidates),
        "merge_decisions_sha256": artifact_hash(job.evidence_dir / "merge-decisions.json") if decisions else None,
        "output_hashes": _output_hashes(job),
    }
    write_json(job.evidence_dir / "review.json", report)
    if report["passed"]:
        (job.evidence_dir / "repair-scope.json").unlink(missing_ok=True)
        (job.evidence_dir / "repair-scope-state.json").unlink(missing_ok=True)
    (job.evidence_dir / "review.html").unlink(missing_ok=True)
    update_phase(job.evidence_dir, "reviewed", "validation_completed", {
        "passed": report["passed"], "issue_count": len(issues), "merge_candidates": len(candidates),
    })
    return report


def check_existing(job: Job) -> dict:
    """Check the latest review and outputs without executing extractor code."""
    report = read_json(job.evidence_dir / "review.json")
    current = {
        "source_sha256": source_sha256(job.source), "inventory_sha256": artifact_hash(job.inventory),
        "reference_sha256": artifact_hash(job.reference), "extractor_sha256": artifact_hash(job.main),
    }
    decisions = job.evidence_dir / "merge-decisions.json"
    if decisions.is_file():
        current["merge_decisions_sha256"] = artifact_hash(decisions)
    stale = [key for key, value in current.items() if report.get(key) != value]
    changed = [name for name, digest in report.get("output_hashes", {}).items()
               if not (job.output_dir / name).is_file() or artifact_hash(job.output_dir / name) != digest]
    return {
        "spec": "pdf-extractor-pdf/existing-review-check@1.0",
        "passed": bool(report.get("passed")) and not stale and not changed,
        "review_passed": bool(report.get("passed")), "stale_inputs": stale, "changed_outputs": changed,
    }


def _validate_result(job: Job, result: dict, inventory: dict, reference: dict, evidence: list[dict]) -> list[dict]:
    issues = []
    if result.get("source_sha256") != source_sha256(job.source):
        issues.append(_issue("source_hash", "extraction_agent", "Result source hash does not match the PDF."))
    actual = {item.get("id"): item for item in result.get("tables", [])}
    inventories = {item["id"]: item for item in inventory["tables"]}
    references = {item["id"]: item for item in reference["tables"]}
    if set(actual) != set(inventories):
        issues.append(_issue("inventory_coverage", "extraction_agent", "Result table IDs do not match Inventory."))
    for table_id in sorted(set(inventories) & set(actual) & set(references)):
        issues.extend(_validate_table(actual[table_id], inventories[table_id], references[table_id], evidence))
    return issues


def _validate_table(actual: dict, inventory: dict, expected: dict, evidence: list[dict]) -> list[dict]:
    issues, rows, columns = [], actual.get("rows", []), actual.get("columns", [])
    table_id = actual["id"]
    all_evidence = _evidence_refs(evidence, {table_id})
    if columns != expected["columns"]:
        issues.append(_issue("header_mismatch", "main_agent", f"{table_id}: header differs.", table_id=table_id,
                             extractor_sample=columns, qa_reference=expected["columns"],
                             cell_diffs=cell_diffs(columns, expected["columns"], expected["columns"]), evidence_refs=all_evidence))
    if len(rows) != expected["row_count"]:
        issues.append(_issue("row_count_mismatch", "main_agent", f"{table_id}: row count differs.", table_id=table_id,
                             extractor_row_count=len(rows), qa_row_count=expected["row_count"], evidence_refs=all_evidence))
    provenance = actual.get("provenance")
    for sample in expected["samples"]:
        index, qa_row = sample["row_index"], sample["values"]
        extractor_row = rows[index] if index < len(rows) else None
        if extractor_row is None or normalized_values(extractor_row) != normalized_values(qa_row):
            sample_evidence = _sample_evidence(evidence, table_id, provenance, index) or all_evidence
            issues.append(_issue(
                "sample_mismatch", "main_agent", f"{table_id}: QA sample row {index} differs.",
                table_id=table_id, row_index=index, sample_reasons=sample.get("reasons", []),
                extractor_sample=extractor_row, qa_reference=qa_row,
                cell_diffs=cell_diffs(extractor_row or [], qa_row, expected["columns"]), evidence_refs=sample_evidence,
            ))
    segments = {item["id"]: item for item in inventory["segments"]}
    if not isinstance(provenance, list) or len(provenance) != len(rows):
        issues.append(_issue("provenance_alignment", "extraction_agent", f"{table_id}: provenance does not align.", table_id=table_id))
    else:
        for index, item in enumerate(provenance):
            segment = segments.get(item.get("segment_id"))
            if not segment or item.get("page") != segment["page"] or not _bbox_inside(item.get("bbox"), segment["bbox"]):
                issues.append(_issue("invalid_provenance", "extraction_agent", f"{table_id}: invalid provenance row {index}.", table_id=table_id, row_index=index))
                break
    return issues


def _evidence_refs(evidence: list[dict], ids: set[str]) -> list[str]:
    return [_evidence_id(item) for item in evidence if item["table_id"] in ids]


def _evidence_index(evidence: list[dict]) -> dict[str, dict]:
    keys = ["table_id", "segment_id", "page", "image", "image_sha256", "geometry"]
    return {_evidence_id(item): {key: item[key] for key in keys if key in item} for item in evidence}


def _evidence_id(item: dict) -> str:
    return f"{item['table_id']}::{item['segment_id']}"


def _sample_evidence(evidence: list[dict], table_id: str, provenance: object, index: int) -> list[dict]:
    if not isinstance(provenance, list) or index >= len(provenance):
        return []
    segment_id = provenance[index].get("segment_id")
    return _evidence_refs([x for x in evidence if x["segment_id"] == segment_id], {table_id})


def _review_queue(cases: list[dict], candidates: list[dict]) -> list[dict]:
    queue = [{"kind": "case", "id": item["id"]} for item in cases if item["review_required"]]
    queue.extend({"kind": "merge_candidate", "id": f"{x['left']}::{x['right']}"} for x in candidates if not x.get("resolved"))
    return queue


def _issue(code: str, route: str, message: str, **details) -> dict:
    identity = ":".join(str(x) for x in [details.get("table_id", "global"), code, details.get("row_index", "")])
    return {"id": identity, "code": code, "route": route, "message": message, **details}


def _group_ids(issues: list[dict]) -> dict:
    groups = {}
    for item in issues:
        groups.setdefault(item["route"], []).append(item["id"])
    return groups


def _merge_decisions(job: Job) -> dict:
    path = job.evidence_dir / "merge-decisions.json"
    if not path.is_file():
        return {}
    value = read_json(path)
    if value.get("inventory_sha256") != artifact_hash(job.inventory):
        return {}
    return {(item["left"], item["right"]): item for item in value.get("decisions", [])}


def _bbox_inside(value: object, parent: list) -> bool:
    return isinstance(value, list) and len(value) == 4 and value[0] >= parent[0] and value[1] >= parent[1] and value[2] <= parent[2] and value[3] <= parent[3]


def _canonical(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _output_hashes(job: Job) -> dict[str, str]:
    return {path.name: artifact_hash(path) for path in sorted(job.output_dir.iterdir()) if path.is_file()}
