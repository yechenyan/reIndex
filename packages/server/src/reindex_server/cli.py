from __future__ import annotations

import argparse

import uvicorn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reindex-server")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run the ReIndex API.")
    run.add_argument("--host", default="0.0.0.0")
    run.add_argument("--port", type=int, default=8000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        uvicorn.run("reindex_server.app:app", host=args.host, port=args.port)
    return 0

