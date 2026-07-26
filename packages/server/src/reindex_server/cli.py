from __future__ import annotations

import argparse
import os

import uvicorn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reindex-server")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run the ReIndex API.")
    run.add_argument("--host", default="0.0.0.0")
    run.add_argument("--port", type=int, default=8000)
    commands.add_parser("init-db", help="Install the PostgreSQL and pgvector schema.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        uvicorn.run("reindex_server.app:app", host=args.host, port=args.port)
    if args.command == "init-db":
        from reindex_server.postgres import initialize_database

        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            parser.error("DATABASE_URL is required for init-db")
        initialize_database(database_url)
    return 0
