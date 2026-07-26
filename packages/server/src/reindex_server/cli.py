from __future__ import annotations

import argparse
import json
from pathlib import Path

import uvicorn

from reindex_server.config import database_url_from_environment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reindex-server")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run the ReIndex API.")
    run.add_argument("--host", default="0.0.0.0")
    run.add_argument("--port", type=int, default=8000)
    commands.add_parser("init-db", help="Install the PostgreSQL and pgvector schema.")
    evaluate = commands.add_parser(
        "eval-search", help="Evaluate search against a labeled JSONL dataset."
    )
    evaluate.add_argument("--collection-id", required=True)
    evaluate.add_argument("--dataset", type=Path, required=True)
    evaluate.add_argument(
        "--mode",
        choices=("lexical", "semantic", "hybrid", "all"),
        default="all",
    )
    evaluate.add_argument("--cutoffs", default="5,10")
    evaluate.add_argument("--candidate-limit", type=int, default=100)
    evaluate.add_argument("--lexical-weight", type=float, default=0.5)
    evaluate.add_argument("--semantic-weight", type=float, default=1.0)
    evaluate.add_argument("--rrf-k", type=int, default=60)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        uvicorn.run("reindex_server.app:app", host=args.host, port=args.port)
    if args.command == "init-db":
        from reindex_server.postgres import initialize_database

        database_url = database_url_from_environment()
        if not database_url:
            parser.error("DATABASE_URL is required for init-db")
        initialize_database(database_url)
    if args.command == "eval-search":
        from reindex_server.evaluation import evaluate, load_dataset
        from reindex_server.runtime import service_from_environment

        service, database = service_from_environment()
        if database is None:
            parser.error("DATABASE_URL is required for eval-search")
        try:
            cases = load_dataset(args.dataset)
            cutoffs = tuple(sorted({int(value) for value in args.cutoffs.split(",")}))
            if not cutoffs or min(cutoffs) < 1 or max(cutoffs) > 50:
                parser.error("--cutoffs must contain integers from 1 to 50")
            modes = (
                ("lexical", "semantic", "hybrid")
                if args.mode == "all"
                else (args.mode,)
            )
            report = {
                "collection_id": args.collection_id,
                "dataset": str(args.dataset),
                "results": [
                    evaluate(
                        service,
                        args.collection_id,
                        cases,
                        mode,
                        cutoffs=cutoffs,
                        candidate_limit=args.candidate_limit,
                        lexical_weight=args.lexical_weight,
                        semantic_weight=args.semantic_weight,
                        rrf_k=args.rrf_k,
                    )
                    for mode in modes
                ],
            }
            print(json.dumps(report, ensure_ascii=False, indent=2))
        finally:
            database.close()
    return 0
