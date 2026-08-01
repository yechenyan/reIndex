from __future__ import annotations

import argparse
import json

from reindex_cli import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rei")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check that the ReIndex CLI is available.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        print(json.dumps({"status": "ok", "version": __version__}))
    return 0
