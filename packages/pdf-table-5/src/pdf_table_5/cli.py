from __future__ import annotations

import argparse
import json
from pathlib import Path

from .api import execute, initialize, verify


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdf-table-5")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create parse/ and output/ in a project directory")
    init.add_argument("pdf", type=Path)
    init.add_argument("--project", type=Path, required=True)
    init.add_argument("--pages", help="1-based pages, for example 5,16-17")
    init.add_argument("--force", action="store_true")
    run = commands.add_parser("run", help="Execute or resume the workflow")
    run.add_argument("project", type=Path)
    run.add_argument("--model")
    run.add_argument("--reasoning-effort")
    check = commands.add_parser("verify", help="Re-run deterministic table checks")
    check.add_argument("project", type=Path)
    all_steps = commands.add_parser("all", help="Initialize and execute")
    all_steps.add_argument("pdf", type=Path)
    all_steps.add_argument("--project", type=Path, required=True)
    all_steps.add_argument("--pages", help="1-based pages, for example 5,16-17")
    all_steps.add_argument("--model")
    all_steps.add_argument("--reasoning-effort")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        result = initialize(args.pdf, args.project, force=args.force, pages=args.pages)
    elif args.command == "run":
        result = execute(args.project, model=args.model, reasoning_effort=args.reasoning_effort)
    elif args.command == "verify":
        result = verify(args.project)
    else:
        initialize(args.pdf, args.project, pages=args.pages)
        result = execute(args.project, model=args.model, reasoning_effort=args.reasoning_effort)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("accepted", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
