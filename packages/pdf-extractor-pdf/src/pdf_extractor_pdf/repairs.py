from __future__ import annotations

from pdf_extractor_pdf.agents import generate_agent_briefs
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.reference import reopen_reference
from pdf_extractor_pdf.reference_scaffold import scaffold_reference
from pdf_extractor_pdf.repair_scope import active_scope, create_repair_scope
from pdf_extractor_pdf.workflow import load_state


def begin_qa_repair(job: Job, table_ids: list[str] | None = None) -> dict:
    phase = load_state(job.evidence_dir)["phase"]
    state = active_scope(job)
    resumed = phase in {"inspected", "reference_frozen"} and state is not None
    if resumed:
        _require_matching_scope(state, table_ids)
        scope = {
            "path": str(job.evidence_dir / "repair-scope.json"),
            "route": state["route"], "affected_table_ids": state["affected_table_ids"],
        }
    else:
        scope = create_repair_scope(job, "qa_agent", table_ids)
    if phase != "inspected":
        reopen_reference(job, "scoped QA repair")
    template = scaffold_reference(job)
    briefs = generate_agent_briefs(job)
    return {
        "scope": scope, "repair_status": "resumed" if resumed else "created",
        "reference_template": template, "agent_briefs": briefs,
    }


def _require_matching_scope(scope: dict, table_ids: list[str] | None) -> None:
    if scope.get("route") != "qa_agent":
        raise ValueError("active repair scope is not routed to qa_agent")
    if table_ids is not None and set(table_ids) != set(scope.get("affected_table_ids", [])):
        raise ValueError("requested tables differ from the active QA repair scope")
