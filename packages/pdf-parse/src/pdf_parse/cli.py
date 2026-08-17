from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .project_api import execute, initialize, verify


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="pdf-parse")
    commands = root.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Initialize a PDF parse project")
    init.add_argument("input_pdf", type=Path)
    init.add_argument("--project", type=Path, required=True)
    run = commands.add_parser("run", help="Execute or resume a project")
    run.add_argument("project", type=Path)
    check = commands.add_parser("verify", help="Verify completed artifacts")
    check.add_argument("project", type=Path)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "init":
        result = initialize(args.input_pdf, args.project)
    elif args.command == "run":
        result = execute(args.project)
    else:
        result = verify(args.project)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
