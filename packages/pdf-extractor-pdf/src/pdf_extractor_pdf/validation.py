from __future__ import annotations

import json

from pdf_extractor_pdf.artifacts import artifact_hash, read_json
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.merge_detection import merge_candidates
from pdf_extractor_pdf.models import source_sha256
from pdf_extractor_pdf.review_cases import build_review_cases
from pdf_extractor_pdf.repair_scope import scope_violations
from pdf_extractor_pdf.result_validation import validate_result
from pdf_extractor_pdf.runner import _write_outputs, invoke_twice
from pdf_extractor_pdf.review_history import write_versioned_review
from pdf_extractor_pdf.workflow import update_phase


def validate(job: Job) -> dict:
    first, second = invoke_twice(job)
    inventory, reference = read_json(job.inventory), read_json(job.reference)
    evidence = read_json(job.evidence_dir / "segments" / "manifest.json")["segments"]
    issues = []
    if _canonical(first) != _canonical(second):
        issues.append(_issue("nondeterministic_output", "extraction_agent", "Two extractor runs differ."))
    result_issues, format_differences = validate_result(job, first, inventory, reference, evidence)
    issues.extend(result_issues)
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
        "spec": "pdf-extractor-pdf/review@4.0", "review_target": "main_agent",
        "passed": not issues and not blocking, "deterministic": _canonical(first) == _canonical(second),
        "source_sha256": source_sha256(job.source), "inventory_sha256": artifact_hash(job.inventory),
        "reference_sha256": artifact_hash(job.reference), "extractor_sha256": artifact_hash(job.main),
        "summary": {
            "issue_count": len(issues), "case_count": len(cases),
            "format_difference_count": len(format_differences),
            "deterministically_routed_cases": sum(x["route"] != "main_agent" for x in cases),
            "main_agent_case_reviews": sum(x["route"] == "main_agent" for x in cases),
            "merge_reviews": sum(not x.get("resolved") for x in candidates),
        },
        "issues": issues, "format_differences": format_differences,
        "review_cases": cases, "repair_plan": repair_plan,
        "issue_groups": _group_ids(issues), "merge_candidates": candidates,
        "evidence_index": _evidence_index(evidence),
        "review_queue": _review_queue(cases, candidates),
        "merge_decisions_sha256": artifact_hash(job.evidence_dir / "merge-decisions.json") if decisions else None,
        "output_hashes": _output_hashes(job),
    }
    report = write_versioned_review(job, report)
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


def _evidence_refs(evidence: list[dict], ids: set[str]) -> list[str]:
    return [_evidence_id(item) for item in evidence if item["table_id"] in ids]


def _evidence_index(evidence: list[dict]) -> dict[str, dict]:
    keys = ["table_id", "segment_id", "page", "image", "image_sha256", "geometry"]
    return {_evidence_id(item): {key: item[key] for key in keys if key in item} for item in evidence}


def _evidence_id(item: dict) -> str:
    return f"{item['table_id']}::{item['segment_id']}"


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


def _canonical(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _output_hashes(job: Job) -> dict[str, str]:
    return {path.name: artifact_hash(path) for path in sorted(job.output_dir.iterdir()) if path.is_file()}
