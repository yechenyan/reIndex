from __future__ import annotations

from pathlib import Path

from reindex_cli.api import ApiClient
from reindex_cli.checkout import local_manifest
from reindex_cli.collection import resolve_collection
from reindex_cli.config import get_api_url
from reindex_cli.errors import ReIndexError
from reindex_cli.pipeline.runner import check_collection
from reindex_cli.remote_state import (
    cache_manifest,
    load_cached_manifest,
    load_conflicts,
    resolve_remote,
    update_remote,
    write_remote,
)
from reindex_cli.transport import build_transport_manifest, manifest_changes


def push_collection(
    path: Path,
    api_url: str | None = None,
    *,
    message: str | None = None,
    dry_run: bool = False,
) -> dict:
    context = resolve_collection(path)
    if load_conflicts(context.root):
        raise ReIndexError(
            "Unresolved local conflict; resolve it and run pull --continue"
        )
    checked = check_collection(context)
    if checked["status"] != "valid":
        raise ReIndexError("Collection inputs are stale; run rei scan before push")
    manifest, blobs = build_transport_manifest(context)
    url = get_api_url(api_url)
    state = _optional_remote(context.root)
    if state and state.get("collection_id") not in {None, context.collection_id}:
        raise ReIndexError("Local Collection ID differs from configured remote")
    result = _publish(
        ApiClient(url),
        name=context.state["name"],
        collection_id=context.collection_id,
        base_version_id=state.get("base_version_id") if state else None,
        manifest=manifest,
        blobs=blobs,
        message=message or "Publish Collection",
        dry_run=dry_run,
    )
    version_id = result.get("version_id") or result.get("head_version_id")
    if not dry_run:
        cache_manifest(context.root, version_id, manifest)
        write_remote(
            context.root,
            {
                "name": context.state["name"],
                "collection_id": context.collection_id,
                "api_url": url,
                "package_hash": result.get("package_hash"),
                "base_version_id": version_id,
                "head_version_id": version_id,
                "node_dir": context.output_dir.relative_to(context.root).as_posix(),
                "kind": "authoring",
            },
        )
    return {
        **result,
        "version_id": version_id,
        "uploaded_blobs": result.get("uploaded_blobs", 0),
    }


def fetch_collection(path: Path, api_url: str | None = None) -> dict:
    root, state = resolve_remote(path, explicit_url=api_url)
    fetched = ApiClient(state["api_url"]).json(
        "/v1/fetch", {"collection": state["name"]}
    )
    head = fetched["version"]["version_id"]
    cache_manifest(root, head, fetched["manifest"])
    updated = update_remote(
        root,
        collection_id=fetched["collection_id"],
        head_version_id=head,
        api_url=state["api_url"],
    )
    return {
        "status": "ready",
        "name": fetched["name"],
        "collection_id": fetched["collection_id"],
        "base_version_id": updated.get("base_version_id"),
        "head_version_id": head,
        "version": fetched["version"],
    }


def history_collection(
    target: str,
    api_url: str | None = None,
    *,
    version_id: str | None,
    limit: int,
    cursor: str | None,
) -> dict:
    name, url = _name_and_url(target, api_url)
    if version_id:
        fetched = ApiClient(url).json(
            "/v1/fetch", {"collection": name, "version_id": version_id}
        )
        return fetched["version"]
    payload = {"collection": name, "limit": limit}
    if cursor:
        payload["cursor"] = cursor
    return ApiClient(url).json("/v1/history", payload)


def diff_collection(
    target: str,
    api_url: str | None = None,
    *,
    remote: bool,
    from_version: str | None,
    to_version: str | None,
) -> dict:
    if from_version and to_version:
        name, url = _name_and_url(target, api_url)
        before = ApiClient(url).json(
            "/v1/fetch", {"collection": name, "version_id": from_version}
        )
        after = ApiClient(url).json(
            "/v1/fetch", {"collection": name, "version_id": to_version}
        )
        return {
            "status": "ready",
            "from_version_id": from_version,
            "to_version_id": to_version,
            **manifest_changes(before["manifest"], after["manifest"]),
        }
    root, state = resolve_remote(Path(target), explicit_url=api_url)
    base_id = state.get("base_version_id")
    base = load_cached_manifest(root, base_id) if base_id else None
    if remote:
        fetched = ApiClient(state["api_url"]).json(
            "/v1/fetch", {"collection": state["name"]}
        )
        other = fetched["manifest"]
        label = fetched["version"]["version_id"]
    else:
        other = local_manifest(root, state)
        label = "local"
    return {
        "status": "ready",
        "base_version_id": base_id,
        "target": label,
        **manifest_changes(base, other),
    }


def rollback_collection(
    name: str,
    version_id: str,
    api_url: str | None = None,
    *,
    message: str | None,
    dry_run: bool,
) -> dict:
    url = get_api_url(api_url)
    client = ApiClient(url)
    target = client.json("/v1/fetch", {"collection": name, "version_id": version_id})
    head = client.json("/v1/fetch", {"collection": name})
    blobs = {item["sha256"]: None for item in target["manifest"]["files"]}
    return _publish(
        client,
        name=name,
        collection_id=target["collection_id"],
        base_version_id=head["version"]["version_id"],
        manifest=target["manifest"],
        blobs=blobs,
        message=message or f"Rollback to {version_id}",
        dry_run=dry_run,
        operation="rollback",
        source_version_id=version_id,
    )


def search_remote(query, start, remote, api_url, mode, limit) -> dict:
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


def _publish(
    client,
    *,
    name,
    collection_id,
    base_version_id,
    manifest,
    blobs,
    message,
    dry_run,
    operation="publish",
    source_version_id=None,
):
    payload = {
        "name": name,
        "collection_id": collection_id,
        "base_version_id": base_version_id,
        "message": message,
        "operation": operation,
        "source_version_id": source_version_id,
        "dry_run": dry_run,
        "manifest": manifest,
    }
    planned = client.json("/v1/push", payload)
    if planned.get("no_op") or dry_run:
        return planned
    upload_id = planned["upload_id"]
    for item in planned["missing_blobs"]:
        path = blobs.get(item["sha256"])
        if path is None:
            raise ReIndexError(f"Server is missing retained blob: {item['sha256']}")
        client.upload_blob(upload_id, item["sha256"], path)
    return client.json("/v1/push/commit", {"upload_id": upload_id})


def _name_and_url(target: str, api_url: str | None) -> tuple[str, str]:
    path = Path(target)
    if path.exists() or target in {".", ".."}:
        _root, state = resolve_remote(path, explicit_url=api_url)
        return state["name"], state["api_url"]
    return target, get_api_url(api_url)


def _optional_remote(root: Path) -> dict | None:
    try:
        return resolve_remote(root)[1]
    except ReIndexError as error:
        if "No remote is configured" in str(error):
            return None
        raise
