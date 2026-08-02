from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

from reindex_cli import __version__
from reindex_cli.checkout import pull_collection
from reindex_cli.collection import create_collection, resolve_collection
from reindex_cli.config import set_api_url
from reindex_cli.errors import ReIndexError
from reindex_cli.get_ops import get_resource
from reindex_cli.pipeline.runner import check_collection, inspect_collection, run_scan
from reindex_cli.remote_ops import (
    diff_collection,
    fetch_collection,
    history_collection,
    push_collection,
    rollback_collection,
    search_remote,
)
from reindex_cli.skills import AGENTS, manage_skills


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rei", description="Build and use ReIndex knowledge Collections."
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Initialize ReIndex and Agent skills.")
    init.add_argument("path", type=Path, nargs="?", default=Path.cwd())
    init.add_argument("--name")
    init.add_argument("--agent", choices=AGENTS, default="codex")
    init.add_argument("--codex-home", type=Path)
    create = commands.add_parser("create", help="Create only local identity state.")
    create.add_argument("path", type=Path)
    create.add_argument("--name")
    rename = commands.add_parser("rename", help="Change the Collection name.")
    rename.add_argument("path", type=Path)
    rename.add_argument("name")
    inspect = commands.add_parser("inspect", help="Inspect inputs without writing.")
    inspect.add_argument("path", type=Path)
    scan = commands.add_parser("scan", help="Compile a validated local package.")
    scan.add_argument("path", type=Path)
    scan.add_argument("--collection-root", type=Path)
    check = commands.add_parser("check", help="Validate the current package.")
    check.add_argument("path", type=Path)
    skills = commands.add_parser("skills", help="Manage bundled Agent skills.")
    skill_commands = skills.add_subparsers(dest="skill_command", required=True)
    for name in ("install", "update"):
        command = skill_commands.add_parser(name)
        command.add_argument("--agent", choices=AGENTS, default="codex")
        command.add_argument("--workspace-root", type=Path, default=Path.cwd())
        command.add_argument("--codex-home", type=Path)
        command.add_argument("--force", action="store_true")
    api = commands.add_parser("set-api", help="Persist the default API URL.")
    api.add_argument("url")
    push = commands.add_parser(
        "push", help="Incrementally publish a validated Collection."
    )
    push.add_argument("path", type=Path, nargs="?", default=Path.cwd())
    push.add_argument("--api-url")
    push.add_argument("--message")
    push.add_argument("--dry-run", action="store_true")
    fetch = commands.add_parser(
        "fetch", help="Fetch remote version metadata without changing local files."
    )
    fetch.add_argument("path", type=Path, nargs="?", default=Path.cwd())
    fetch.add_argument("--api-url")
    pull = commands.add_parser(
        "pull", help="Create or update a Node-only ReIndex checkout."
    )
    pull.add_argument("name", nargs="?")
    destination = pull.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path)
    destination.add_argument("--path", type=Path)
    pull.add_argument("--api-url")
    pull.add_argument("--version", dest="version_id")
    pull.add_argument("--continue", dest="continue_pull", action="store_true")
    history = commands.add_parser("history", help="List or inspect remote versions.")
    history.add_argument("target", nargs="?", default=".")
    history.add_argument("--api-url")
    history.add_argument("--version", dest="version_id")
    history.add_argument("--limit", type=int, default=20)
    history.add_argument("--cursor")
    diff = commands.add_parser("diff", help="Compare local or remote manifests.")
    diff.add_argument("target", nargs="?", default=".")
    diff.add_argument("--api-url")
    diff.add_argument("--remote", action="store_true")
    diff.add_argument("--from", dest="from_version")
    diff.add_argument("--to", dest="to_version")
    rollback = commands.add_parser(
        "rollback", help="Publish a retained version as a new active version."
    )
    rollback.add_argument("name")
    rollback.add_argument("version_id")
    rollback.add_argument("--api-url")
    rollback.add_argument("--message")
    rollback.add_argument("--dry-run", action="store_true")
    search = commands.add_parser("search", help="Search a remote Collection.")
    search.add_argument("query")
    search.add_argument("--path", type=Path, default=Path.cwd())
    search.add_argument("--remote")
    search.add_argument("--api-url")
    search.add_argument(
        "--mode", choices=("lexical", "semantic", "hybrid"), default="lexical"
    )
    search.add_argument("--limit", type=int, default=10)
    get = commands.add_parser("get", help="Reuse or fetch one exact resource.")
    get.add_argument("reference")
    get.add_argument("--path", type=Path, default=Path.cwd())
    get.add_argument("--remote")
    get.add_argument("--api-url")
    get.add_argument("--target", choices=("card", "source", "content", "asset"))
    get.add_argument("--asset-ordinal", type=int)
    get.add_argument("--output", type=Path)
    get.add_argument("--version", dest="version_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        output = _execute(args)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (ReIndexError, OSError, ValueError, httpx.HTTPError) as error:
        print(
            json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1


def _execute(args) -> dict:
    if args.command == "init":
        root = args.path.expanduser().resolve()
        collection = create_collection(root, args.name)
        skills = manage_skills(
            args.agent,
            root,
            update=True,
            codex_home=args.codex_home,
        )
        return {
            "status": "ready",
            **collection,
            "collection_id": collection["id"],
            "skills": [vars(item) for item in skills],
        }
    if args.command in {"create", "rename"}:
        name = args.name
        result = create_collection(args.path.expanduser().resolve(), name)
        return {
            "status": "ready",
            **result,
            "collection_id": result["id"],
            "renamed": args.command == "rename",
        }
    if args.command == "skills":
        results = manage_skills(
            args.agent,
            args.workspace_root.expanduser().resolve(),
            update=args.skill_command == "update",
            force=args.force,
            codex_home=args.codex_home,
        )
        return {"status": "ready", "skills": [vars(item) for item in results]}
    if args.command == "set-api":
        return {"status": "ready", "api_url": set_api_url(args.url)}
    if args.command == "push":
        return push_collection(
            args.path,
            args.api_url,
            message=args.message,
            dry_run=args.dry_run,
        )
    if args.command == "fetch":
        return fetch_collection(args.path, args.api_url)
    if args.command == "pull":
        if args.continue_pull and args.path is None:
            raise ReIndexError("pull --continue requires --path")
        if args.continue_pull and (
            args.name is not None or args.version_id is not None
        ):
            raise ReIndexError("pull --continue does not accept name or --version")
        if args.path is not None and args.name is not None:
            raise ReIndexError("pull --path does not accept a Collection name")
        if args.path is not None and args.output is not None:
            raise ReIndexError("pull accepts only one of --path and --output")
        if args.path is not None and args.version_id is not None:
            raise ReIndexError("pull --version is only valid for a new checkout")
        if args.path is None and args.name is None:
            raise ReIndexError("pull requires a Collection name or --path")
        return pull_collection(
            args.name,
            args.output,
            args.api_url,
            path=args.path,
            version_id=args.version_id,
            continue_pull=args.continue_pull,
        )
    if args.command == "history":
        if args.limit < 1 or args.limit > 100:
            raise ReIndexError("history --limit must be between 1 and 100")
        return history_collection(
            args.target,
            args.api_url,
            version_id=args.version_id,
            limit=args.limit,
            cursor=args.cursor,
        )
    if args.command == "diff":
        if bool(args.from_version) != bool(args.to_version):
            raise ReIndexError("diff requires both --from and --to")
        if args.remote and args.from_version:
            raise ReIndexError("diff --remote cannot be combined with --from/--to")
        return diff_collection(
            args.target,
            args.api_url,
            remote=args.remote,
            from_version=args.from_version,
            to_version=args.to_version,
        )
    if args.command == "rollback":
        return rollback_collection(
            args.name,
            args.version_id,
            args.api_url,
            message=args.message,
            dry_run=args.dry_run,
        )
    if args.command == "search":
        return search_remote(
            args.query, args.path, args.remote, args.api_url, args.mode, args.limit
        )
    if args.command == "get":
        return get_resource(
            args.reference,
            args.path,
            target=args.target,
            asset_ordinal=args.asset_ordinal,
            output=args.output,
            remote=args.remote,
            api_url=args.api_url,
            version_id=args.version_id,
        )
    context = resolve_collection(
        args.path, args.collection_root if args.command == "scan" else None
    )
    if args.command == "inspect":
        return inspect_collection(context)
    if args.command == "scan":
        return run_scan(context)
    return check_collection(context)
