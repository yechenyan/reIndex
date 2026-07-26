from __future__ import annotations

import argparse
import json
import sys

from reindex_cli import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reindex",
        description="Build, upload, and query ReIndex knowledge packages.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("doctor", help="Check the local CLI installation.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        print(json.dumps({"status": "ok", "version": __version__}))
        return 0
    parser.print_help(sys.stderr)
    return 0

