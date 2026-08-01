from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from reindex_cli import __version__
from reindex_cli.collection import create_collection, resolve_collection
from reindex_cli.errors import ReIndexError
from reindex_cli.pipeline.runner import check_collection, inspect_collection, run_scan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rei", description="Compile local files into ReIndex packages."
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser(
        "create", help="Create a Collection identity boundary."
    )
    create.add_argument("collection_dir", type=Path)
    inspect = commands.add_parser(
        "inspect",
        help="Inspect Collection context and effective inputs without writing.",
    )
    inspect.add_argument("path", type=Path)
    scan = commands.add_parser(
        "scan", help="Compile files into a validated ReIndex package."
    )
    scan.add_argument("path", type=Path)
    scan.add_argument("--collection-root", type=Path)
    check = commands.add_parser(
        "check", help="Validate the current package without rebuilding it."
    )
    check.add_argument("path", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.command == "create":
            root = args.collection_dir.expanduser().resolve()
            result = create_collection(root)
            output = {
                "status": "ready",
                "created": result["created"],
                "collection_root": str(root),
                "collection_id": result["id"],
            }
        elif args.command == "inspect":
            output = inspect_collection(resolve_collection(args.path))
        elif args.command == "scan":
            output = run_scan(resolve_collection(args.path, args.collection_root))
        else:
            output = check_collection(resolve_collection(args.path))
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (ReIndexError, OSError, ValueError) as error:
        print(
            json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
