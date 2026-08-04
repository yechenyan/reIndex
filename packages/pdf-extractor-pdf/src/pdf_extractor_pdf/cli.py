from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from pdf_extractor_pdf.cache import verify_cache
from pdf_extractor_pdf.agents import generate_agent_briefs
from pdf_extractor_pdf.decisions import resolve_merges
from pdf_extractor_pdf.evidence import prepare, render_pages
from pdf_extractor_pdf.gates import finalize
from pdf_extractor_pdf.inspection import inspect_inventory
from pdf_extractor_pdf.inventory import freeze_inventory, reopen_inventory
from pdf_extractor_pdf.inventory_audit import audit_inventory
from pdf_extractor_pdf.job import load_job
from pdf_extractor_pdf.metrics import finish_stage, measure, metrics_report, record_agent, start_stage
from pdf_extractor_pdf.reference import freeze_reference, reopen_reference
from pdf_extractor_pdf.reference_scaffold import plan_reference, scaffold_reference
from pdf_extractor_pdf.repair_scope import create_repair_scope
from pdf_extractor_pdf.runner import execute
from pdf_extractor_pdf.scaffold import initialize_project
from pdf_extractor_pdf.skill import bundled_skill_path, install_skill
from pdf_extractor_pdf.validation import check_existing, validate
from pdf_extractor_pdf.workflow import load_state


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="pdf-extractor-pdf")
    commands = root.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("project", type=Path)
    init.add_argument("source", type=Path)
    init.add_argument("--request", default="Extract all tables from the PDF.")
    init.add_argument("--force", action="store_true")
    for name in ["prepare", "inspect", "run", "validate", "check", "verify-cache", "finalize", "status"]:
        child = commands.add_parser(name)
        child.add_argument("job", type=Path)
    pages = commands.add_parser("render-pages")
    pages.add_argument("job", type=Path)
    pages.add_argument("pages", nargs="+", type=int)
    pages.add_argument("--dpi", type=int)
    audit = commands.add_parser("audit-inventory")
    audit.add_argument("job", type=Path)
    audit.add_argument("draft", type=Path)
    for name in ["freeze-inventory", "freeze-reference"]:
        child = commands.add_parser(name)
        child.add_argument("job", type=Path)
        child.add_argument("draft", type=Path)
    scaffold = commands.add_parser("scaffold-reference")
    scaffold.add_argument("job", type=Path)
    plan = commands.add_parser("plan-reference")
    plan.add_argument("job", type=Path)
    plan.add_argument("draft", type=Path)
    decisions = commands.add_parser("resolve-merges")
    decisions.add_argument("job", type=Path)
    decisions.add_argument("draft", type=Path)
    repair = commands.add_parser("repair-scope")
    repair.add_argument("job", type=Path)
    repair.add_argument("--route", required=True, choices=["finder_agent", "extraction_agent", "qa_agent", "main_agent"])
    repair.add_argument("--tables", nargs="*")
    for name in ["reopen-inventory", "reopen-reference"]:
        child = commands.add_parser(name)
        child.add_argument("job", type=Path)
        child.add_argument("--reason", required=True)
    agent = commands.add_parser("record-agent")
    agent.add_argument("job", type=Path)
    agent.add_argument("metric", type=Path)
    stage_start = commands.add_parser("stage-start")
    stage_start.add_argument("job", type=Path)
    stage_start.add_argument("stage")
    stage_start.add_argument("--role", required=True)
    stage_start.add_argument("--model", required=True)
    stage_start.add_argument("--run-id")
    stage_start.add_argument("--agent-id", required=True)
    stage_finish = commands.add_parser("stage-finish")
    stage_finish.add_argument("job", type=Path)
    stage_finish.add_argument("run_id")
    stage_finish.add_argument("--status", choices=["completed", "failed", "blocked"], default="completed")
    stage_finish.add_argument("--waiting-seconds", type=float, default=0)
    stage_finish.add_argument("--token-input", type=int)
    stage_finish.add_argument("--token-output", type=int)
    stage_finish.add_argument("--notes")
    metrics = commands.add_parser("metrics-report")
    metrics.add_argument("job", type=Path)
    briefs = commands.add_parser("agent-briefs")
    briefs.add_argument("job", type=Path)
    commands.add_parser("skill-path")
    install = commands.add_parser("install-skill")
    install.add_argument("workspace", type=Path)
    install.add_argument("--force", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    started = perf_counter()
    if args.command == "init":
        job_path = initialize_project(args.project, args.source, args.request, args.force)
        briefs = generate_agent_briefs(load_job(job_path))
        return _print({"job": str(job_path), "agent_briefs": briefs, "elapsed_seconds": round(perf_counter() - started, 6)})
    if args.command == "skill-path":
        return _print({"path": str(bundled_skill_path())})
    if args.command == "install-skill":
        target, status = install_skill(args.workspace, args.force)
        return _print({"path": str(target), "status": status})
    job = load_job(args.job)
    with measure(job.evidence_dir, args.command) as metric:
        value = _dispatch(args, job)
    payload = value if isinstance(value, dict) else {"result": value}
    payload["elapsed_seconds"] = metric["elapsed_seconds"]
    _print(payload)
    if args.command in {"validate", "check", "verify-cache"} and payload.get("passed", payload.get("ok")) is False:
        return 2
    return 0


def _dispatch(args: argparse.Namespace, job):
    if args.command == "prepare":
        return prepare(job)
    if args.command == "render-pages":
        return {"pages": render_pages(job, args.pages, args.dpi)}
    if args.command == "audit-inventory":
        return audit_inventory(job, args.draft)
    if args.command == "freeze-inventory":
        return freeze_inventory(job, args.draft)
    if args.command == "inspect":
        return inspect_inventory(job)
    if args.command == "scaffold-reference":
        return scaffold_reference(job)
    if args.command == "plan-reference":
        return plan_reference(job, args.draft)
    if args.command == "freeze-reference":
        return freeze_reference(job, args.draft)
    if args.command == "run":
        result = execute(job)
        return {"tables": len(result["tables"]), "rows": sum(len(x["rows"]) for x in result["tables"])}
    if args.command == "validate":
        return validate(job)
    if args.command == "check":
        return check_existing(job)
    if args.command == "verify-cache":
        return verify_cache(job)
    if args.command == "resolve-merges":
        return resolve_merges(job, args.draft)
    if args.command == "repair-scope":
        return create_repair_scope(job, args.route, args.tables)
    if args.command == "finalize":
        return finalize(job)
    if args.command == "reopen-inventory":
        return reopen_inventory(job, args.reason)
    if args.command == "reopen-reference":
        return reopen_reference(job, args.reason)
    if args.command == "record-agent":
        return {"path": str(record_agent(job.evidence_dir, json.loads(args.metric.read_text(encoding="utf-8"))))}
    if args.command == "stage-start":
        scope_path = job.evidence_dir / "repair-scope.json"
        scope = json.loads(scope_path.read_text(encoding="utf-8")) if scope_path.is_file() else {}
        return start_stage(
            job.evidence_dir, args.stage, args.role, args.model, args.run_id,
            agent_id=args.agent_id, workflow_phase=load_state(job.evidence_dir)["phase"],
            table_ids=scope.get("affected_table_ids") if args.role != "main_agent" else None,
        )
    if args.command == "stage-finish":
        token_usage = None
        if args.token_input is not None or args.token_output is not None:
            token_usage = {"input": args.token_input or 0, "output": args.token_output or 0}
            token_usage["total"] = token_usage["input"] + token_usage["output"]
        return finish_stage(
            job.evidence_dir, args.run_id, args.status,
            waiting_seconds=args.waiting_seconds, token_usage=token_usage, notes=args.notes,
        )
    if args.command == "metrics-report":
        return metrics_report(job.evidence_dir)
    if args.command == "agent-briefs":
        return generate_agent_briefs(job)
    if args.command == "status":
        return load_state(job.evidence_dir)
    raise AssertionError(args.command)


def _print(value: dict) -> int:
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
