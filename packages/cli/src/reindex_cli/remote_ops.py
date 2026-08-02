from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from reindex_cli.api import ApiClient
from reindex_cli.archives import build_push_archives, extract_node_archive
from reindex_cli.collection import resolve_collection
from reindex_cli.config import get_api_url
from reindex_cli.errors import ReIndexError
from reindex_cli.pipeline.runner import check_collection
from reindex_cli.remote_state import resolve_remote, write_remote


def push_collection(path: Path, api_url: str | None = None) -> dict:
    context = resolve_collection(path)
    checked = check_collection(context)
    if checked["status"] != "valid":
        raise ReIndexError("Collection inputs are stale; run rei scan before push")
    package, sources, temporary = build_push_archives(context)
    url = get_api_url(api_url)
    try:
        result = ApiClient(url).push(context.state["name"], package, sources)
    finally:
        temporary.cleanup()
    write_remote(
        context.root,
        {
            "name": result["name"],
            "collection_id": result["collection_id"],
            "api_url": url,
            "package_hash": result["package_hash"],
            "node_dir": context.output_dir.relative_to(context.root).as_posix(),
            "kind": "authoring",
        },
    )
    return result


def pull_collection(
    name: str,
    output: Path,
    api_url: str | None = None,
    *,
    force: bool = False,
) -> dict:
    url = get_api_url(api_url)
    content, headers = ApiClient(url).bytes("/v1/pull", {"collection": name})
    destination = output.expanduser().resolve()
    if destination.exists() and any(destination.iterdir()) and not force:
        raise ReIndexError(f"Pull destination is not empty: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent)
    )
    try:
        node_dir = staging / "reIndex" / name
        count = extract_node_archive(content, node_dir)
        write_remote(
            staging,
            {
                "name": name,
                "api_url": url,
                "package_hash": _header(headers, "x-reindex-package-hash"),
                "node_dir": f"reIndex/{name}",
                "kind": "node-checkout",
            },
        )
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        "status": "ready",
        "name": name,
        "output": str(destination),
        "node_dir": str(destination / "reIndex" / name),
        "nodes": count,
        "package_hash": _header(headers, "x-reindex-package-hash"),
    }


def search_remote(
    query: str,
    start: Path,
    remote: str | None,
    api_url: str | None,
    mode: str,
    limit: int,
) -> dict:
    _root, state = resolve_remote(start, remote, api_url)
    return ApiClient(state["api_url"]).json(
        "/v1/search",
        {
            "collection": state["name"],
            "query": query,
            "mode": mode,
            "limit": limit,
            "candidate_limit": max(100, limit),
        },
    )


def _header(headers: dict[str, str], name: str) -> str | None:
    return next((value for key, value in headers.items() if key.lower() == name), None)
