from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pdf_extractor_pdf.artifacts import artifact_hash, read_json, write_json
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.workflow import require_phase


def create_repair_scope(job: Job, route: str, table_ids: list[str] | None = None) -> dict:
    require_phase(job.evidence_dir, "reviewed", "complete")
    review = read_json(job.evidence_dir / "review.json")
    affected = {case["table_id"] for case in review.get("review_cases", []) if case.get("table_id")}
    planned = set(review.get("repair_plan", {}).get(route, []))
    selected = set(table_ids or planned)
    inventory, reference = read_json(job.inventory), read_json(job.reference)
    all_ids = {item["id"] for item in inventory["tables"]}
    post_review = bool(review.get("passed") and table_ids)
    allowed = all_ids if post_review else affected
    if not selected or not selected.issubset(allowed):
        raise ValueError("repair scope tables must be non-empty and present in current review cases")
    result = read_json(job.output_dir / "result.json")
    evidence_refs = sorted({
        ref for case in review["review_cases"] if case.get("table_id") in selected
        for ref in case.get("evidence_refs", [])
    })
    if post_review:
        evidence_refs = _table_evidence_refs(job, selected)
    scope = {
        "spec": "pdf-extractor-pdf/repair-scope@1.0", "review_sha256": artifact_hash(job.evidence_dir / "review.json"),
        "route": route, "affected_table_ids": sorted(selected), "evidence_refs": evidence_refs,
        "origin": "post_review_explicit" if post_review else "failed_review",
        "instructions": "Agents may inspect and change only affected_table_ids; fixed validation protects every other table.",
    }
    state = {
        **scope, "baseline": {
            "inventory_tables": {x["id"]: x for x in inventory["tables"]},
            "reference_tables": {x["id"]: x for x in reference["tables"]},
            "result_tables": {x["id"]: x for x in result["tables"]},
        },
    }
    path = write_json(job.evidence_dir / "repair-scope.json", scope)
    write_json(job.evidence_dir / "repair-scope-state.json", state)
    archive = job.evidence_dir / "repair-scopes" / f"scope-{artifact_hash(path)[:16]}.json"
    write_json(archive, state)
    return {"path": str(path), "archive": str(archive), "route": route, "affected_table_ids": sorted(selected)}


def active_scope(job: Job) -> dict | None:
    path = job.evidence_dir / "repair-scope-state.json"
    return read_json(path) if path.is_file() else None


def selected_table_ids(job: Job, all_ids: set[str]) -> set[str]:
    scope = active_scope(job)
    if not scope:
        return all_ids
    selected = set(scope.get("affected_table_ids", []))
    if not selected.issubset(all_ids):
        raise ValueError("active repair scope references tables outside current Inventory")
    return selected


def merge_reference_patch(job: Job, supplied: dict[str, dict]) -> list[dict]:
    scope = active_scope(job)
    if not scope:
        return list(supplied.values())
    affected = set(scope["affected_table_ids"])
    if set(supplied) != affected:
        raise ValueError("QA repair draft must contain exactly the affected repair-scope tables")
    baseline = scope["baseline"]["reference_tables"]
    return [supplied.get(table_id, value) for table_id, value in baseline.items()]


def scope_violations(job: Job, result: dict, inventory: dict, reference: dict) -> list[dict]:
    scope = active_scope(job)
    if not scope:
        return []
    affected = set(scope["affected_table_ids"])
    checks = [
        ("result", "extraction_agent", scope["baseline"]["result_tables"], result.get("tables", [])),
        ("inventory", "finder_agent", scope["baseline"]["inventory_tables"], inventory.get("tables", [])),
        ("reference", "qa_agent", scope["baseline"]["reference_tables"], reference.get("tables", [])),
    ]
    issues = []
    for artifact, route, baseline, current_values in checks:
        current = {item["id"]: item for item in current_values}
        for table_id in sorted(set(baseline) - affected):
            if table_id not in current or _digest(current[table_id]) != _digest(baseline[table_id]):
                issues.append({
                    "id": f"{table_id}:scope_violation:{artifact}", "code": "scope_violation", "route": route,
                    "message": f"{table_id}: unaffected {artifact} changed during scoped repair.",
                    "table_id": table_id, "artifact": artifact, "evidence_refs": [],
                })
    return issues


def _digest(value: dict) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _table_evidence_refs(job: Job, selected: set[str]) -> list[str]:
    manifest = read_json(job.evidence_dir / "segments" / "manifest.json")
    return sorted(
        f"{item['table_id']}::{item['segment_id']}"
        for item in manifest["segments"] if item["table_id"] in selected
    )
