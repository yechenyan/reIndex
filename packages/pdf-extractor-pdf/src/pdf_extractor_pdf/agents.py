from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pdf_extractor_pdf.artifacts import artifact_hash, read_json, write_json
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.metrics import finished_stages
from pdf_extractor_pdf.workflow import load_state

REQUIRED = {
    "main_agent": "review",
    "finder_agent": "discovery",
    "extraction_agent": "extraction",
    "qa_agent": "qa",
}


def generate_agent_briefs(job: Job) -> dict:
    phase = load_state(job.evidence_dir)["phase"]
    root = job.evidence_dir / "agent-tasks"
    root.mkdir(parents=True, exist_ok=True)
    briefs = {
        "main-agent.md": _brief("Main Agent", job, "Own requirements, positional-column ambiguity, merge decisions, and final review. Tables are header-neutral matrices: row 0 is an ordinary source row. Treat format_only differences as non-blocking; route real row/column/content errors only.", "All project evidence and reports.", "Do not author QA source values or invent column names."),
        "finder-agent.md": _brief("Finder Agent", job, "In one dispatch, inspect every page, draft the complete Inventory with positional column_count, run audit-inventory, apply required BBox repairs, attest every reviewed edge, and rerun the audit until it passes. Return only a freeze-ready draft; do not stop after writing the first draft.", "Finder packet, rolling contact sheets, pre-rendered candidate pages, targeted uncertain pages, Inventory audit overlays, and inventory-review.json.", "Do not read extractor code, output, or prior answers. Do not assume row 0 is a header or rerender pages already supplied."),
        "extraction-agent.md": _brief("Extraction Agent", job, "Implement project main.py for the frozen header-neutral matrix Inventory with row provenance and merge policy. Preserve row 0; remove only explicitly repeated leading rows on continuation Segments. Fix wrong row/column alignment in table-specific code. Generated project code has no artificial 200-line limit.", "Frozen Inventory, Segment images, neutral geometry, source PDF.", "Do not read QA reference drafts or frozen reference; do not invent column names or emit a separate header array."),
        "qa-agent.md": _brief("QA Agent", job, "Independently confirm positional column_count, assign exact/text per column, count source rows and repeated leading rows per Segment, decide only unresolved line-wrap candidates, and transcribe planned samples. Row 0 is not implicitly a header. Use exact for numbers/dates/IDs/codes/amounts and text for free text. List every genuinely empty cell in source_blank_indices.", "Frozen Inventory, Segment images, neutral geometry, source PDF, and code-detected line-wrap candidates.", "Do not read extractor code, output, result, or extraction logs. Do not invent column names or change code-classified line-wrap decisions."),
    }
    written = []
    for name, content in briefs.items():
        path = root / name
        path.write_text(content, encoding="utf-8")
        written.append({"role": name.removesuffix(".md"), "path": str(path), "sha256": artifact_hash(path)})
    scope_path = job.evidence_dir / "repair-scope.json"
    manifest = {
        "spec": "pdf-extractor-pdf/agent-briefs@1.0", "phase": phase, "briefs": written,
        "repair_scope": read_json(scope_path) if scope_path.is_file() else None,
    }
    write_json(root / "manifest.json", manifest)
    return manifest


def verify_role_separation(job: Job) -> dict:
    stages = [item for item in finished_stages(job.evidence_dir) if item.get("status") == "completed"]
    matches_by_role = {}
    for role, stage in REQUIRED.items():
        matches = [item for item in stages if item.get("role") == role and item.get("stage") == stage]
        if not matches:
            raise ValueError(f"missing completed Agent stage: {role}/{stage}")
        matches_by_role[role] = matches
    role_ids = {role: {item.get("agent_id") for item in matches} for role, matches in matches_by_role.items()}
    if any(None in ids or len(ids) != 1 for ids in role_ids.values()) or len({next(iter(x)) for x in role_ids.values()}) != 4:
        raise ValueError("main, finder, extraction, and QA must have four distinct agent_id values")
    pairs = [
        (extraction, qa) for extraction in matches_by_role["extraction_agent"]
        for qa in matches_by_role["qa_agent"] if _overlaps(extraction, qa)
    ]
    if job.policy.get("require_parallel_extraction_qa", True) and not pairs:
        raise ValueError("extraction and QA Agent stages must overlap in time")
    extraction, qa = pairs[-1] if pairs else (
        matches_by_role["extraction_agent"][-1], matches_by_role["qa_agent"][-1],
    )
    selected = {
        "main_agent": matches_by_role["main_agent"][-1],
        "finder_agent": matches_by_role["finder_agent"][-1],
        "extraction_agent": extraction, "qa_agent": qa,
    }
    report = {
        "spec": "pdf-extractor-pdf/role-separation@1.0", "ok": True,
        "agents": {role: {key: value for key, value in item.items() if key in {
            "agent_id", "model", "run_id", "stage", "started_at", "ended_at", "wall_seconds",
        }} for role, item in selected.items()},
        "extraction_qa_overlapped": bool(pairs),
        "dispatches": [_stage_summary(item) for item in stages if item.get("role") in REQUIRED],
    }
    write_json(job.evidence_dir / "role-separation.json", report)
    return report


def _brief(title: str, job: Job, objective: str, allowed: str, prohibited: str) -> str:
    scope_path = job.evidence_dir / "repair-scope.json"
    scope = read_json(scope_path) if scope_path.is_file() else None
    repair = ""
    if scope:
        repair = (
            "\n## Repair scope\n\nProcess only these table IDs: "
            + ", ".join(scope["affected_table_ids"])
            + ". Do not inspect or change other tables. Fixed validation protects unaffected outputs.\n"
        )
    return f"""# {title}\n\n## Request\n\n{job.request}\n\n## Objective\n\n{objective}\n\n## Allowed inputs\n\n{allowed}\n\n## Prohibited inputs\n\n{prohibited}\n{repair}\n## Project boundary\n\nWrite only under `{job.project_dir}`; final tables go in `output/` and all other artifacts in `extractor/`.\n"""


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _overlaps(left: dict, right: dict) -> bool:
    return max(_time(left["started_at"]), _time(right["started_at"])) < min(
        _time(left["ended_at"]), _time(right["ended_at"]),
    )


def _stage_summary(item: dict) -> dict:
    keys = {
        "agent_id", "model", "run_id", "stage", "role", "table_ids", "started_at", "ended_at",
        "wall_seconds", "conversation_turns", "repair_rounds", "dispatch_ordinal",
        "dispatch_kind",
    }
    return {key: value for key, value in item.items() if key in keys}
