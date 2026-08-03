from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from pdf_table_codegen.evidence import prepare_evidence
from pdf_table_codegen.freezing import freeze_inventory, freeze_reference
from pdf_table_codegen.inspection import inspect_inventory
from pdf_table_codegen.job import load_job
from pdf_table_codegen.models import source_sha256
from pdf_table_codegen.runner import run_job, verify_job
from pdf_table_codegen.scaffold import build_assertion_hints
from pdf_table_codegen.skill import bundled_skill_path, install_skill


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdf-table-codegen")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "run", "verify"):
        command = sub.add_parser(name)
        command.add_argument("job", type=Path)
    for name in ("freeze-inventory", "freeze-reference"):
        command = sub.add_parser(name)
        command.add_argument("job", type=Path)
        command.add_argument("draft", type=Path)
    for name in ("inspect", "scaffold"):
        command = sub.add_parser(name)
        command.add_argument("job", type=Path)
    sub.add_parser("skill-path")
    install = sub.add_parser("install-skill")
    install.add_argument("workspace", type=Path, nargs="?", default=Path.cwd())
    install.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    started = perf_counter()
    if args.command == "skill-path":
        print(bundled_skill_path())
        return 0
    if args.command == "install-skill":
        path, status = install_skill(args.workspace, force=args.force)
        print(json.dumps({"ok": True, "path": str(path), "status": status}, indent=2))
        return 0
    if args.command == "prepare":
        manifest = prepare_evidence(load_job(args.job))
        value = {
            "ok": True,
            "source_sha256": manifest["source_sha256"],
            "page_count": manifest["page_count"],
            "contacts": manifest["contacts"],
            "table_detector_run": manifest["table_detector_run"],
            "cache_hit": manifest["cache_hit"],
        }
    elif args.command == "freeze-inventory":
        job = load_job(args.job)
        inventory = freeze_inventory(job, args.draft)
        value = {
            "ok": True,
            "path": str(job.inventory),
            "sha256": source_sha256(job.inventory),
            "tables": len(inventory["tables"]),
        }
    elif args.command == "freeze-reference":
        job = load_job(args.job)
        reference = freeze_reference(job, args.draft)
        value = {
            "ok": True,
            "path": str(job.reference),
            "sha256": source_sha256(job.reference),
            "tables": len(reference["tables"]),
        }
    elif args.command == "inspect":
        manifest = inspect_inventory(load_job(args.job))
        value = {
            "ok": True,
            "tables": len({item["table_id"] for item in manifest["segments"]}),
            "segments": len(manifest["segments"]),
        }
    elif args.command == "scaffold":
        hints = build_assertion_hints(load_job(args.job))
        value = {"ok": True, "tables": len(hints["tables"]), "path": "evidence/assertion-hints.json"}
    elif args.command == "run":
        result = run_job(args.job)
        value = {
            "ok": result.qa.ok,
            "extractor_id": result.extractor_id,
            "tables": [
                {"id": table.id, "rows": len(table.rows), "columns": len(table.headers)}
                for table in result.tables
            ],
        }
    else:
        report = verify_job(args.job)
        value = {
            "ok": report["ok"],
            "checks": len(report["checks"]),
            "failed": [item["name"] for item in report["checks"] if not item["ok"]],
        }
    value["elapsed_seconds"] = round(perf_counter() - started, 3)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0 if value.get("ok", True) else 1
