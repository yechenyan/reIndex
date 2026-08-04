from __future__ import annotations


def build_review_cases(issues: list[dict]) -> tuple[list[dict], dict[str, list[str]]]:
    grouped: dict[str, list[dict]] = {}
    for issue in issues:
        key = issue.get("table_id") or f"global::{issue['code']}"
        grouped.setdefault(key, []).append(issue)
    cases, plan = [], {}
    for key, values in sorted(grouped.items()):
        table_id = values[0].get("table_id")
        codes = sorted({item["code"] for item in values})
        route, confidence, hints = _route(codes)
        evidence_refs = sorted({ref for item in values for ref in item.get("evidence_refs", [])})
        case_id = f"case::{table_id or key}"
        case = {
            "id": case_id, "table_id": table_id, "route": route, "route_confidence": confidence,
            "issue_ids": [item["id"] for item in values], "issue_codes": codes,
            "evidence_refs": evidence_refs, "segment_ids": sorted({ref.split("::", 1)[1] for ref in evidence_refs}),
            "root_cause_hints": hints, "review_required": route == "main_agent",
        }
        cases.append(case)
        if table_id:
            plan.setdefault(route, []).append(table_id)
    return cases, {route: sorted(set(ids)) for route, ids in plan.items()}


def _route(codes: list[str]) -> tuple[str, float, list[str]]:
    deterministic = {
        "nondeterministic_output", "source_hash", "inventory_coverage",
        "provenance_alignment", "invalid_provenance", "scope_violation",
    }
    if deterministic.intersection(codes):
        return "extraction_agent", 1.0, ["extractor_contract_or_provenance"]
    if "row_count_mismatch" in codes:
        hints = ["missing_or_extra_rows"]
        if "sample_mismatch" in codes:
            hints.append("row_alignment_shift")
        return "extraction_agent", 0.9, hints
    if "header_mismatch" in codes:
        hints = ["column_schema_or_header_parsing"]
        if "sample_mismatch" in codes:
            hints.append("column_alignment_shift")
        return "extraction_agent", 0.85, hints
    if codes == ["sample_mismatch"]:
        return "main_agent", 0.5, ["extractor_or_qa_transcription"]
    return "main_agent", 0.4, ["unclassified"]
