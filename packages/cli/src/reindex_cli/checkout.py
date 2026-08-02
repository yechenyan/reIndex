from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from reindex_cli.api import ApiClient
from reindex_cli.archives import extract_node_archive
from reindex_cli.collection import resolve_collection
from reindex_cli.config import get_api_url
from reindex_cli.errors import ReIndexError
from reindex_cli.remote_state import (
    cache_manifest,
    clear_conflicts,
    load_cached_manifest,
    load_conflicts,
    resolve_remote,
    update_remote,
    write_conflicts,
    write_remote,
)
from reindex_cli.transport import (
    build_transport_manifest,
    changed_keys,
    manifest_changes,
)
from reindex_cli.util import sha256_file


def pull_collection(
    name: str | None,
    output: Path | None,
    api_url: str | None = None,
    *,
    path: Path | None,
    version_id: str | None,
    continue_pull: bool,
) -> dict:
    if path is None:
        if name is None:
            raise ReIndexError("Pull requires a Collection name")
        destination = (output or Path(name)).expanduser().resolve()
        return _checkout(
            name, destination, get_api_url(api_url), version_id, replace=False
        )
    root, state = resolve_remote(path, explicit_url=api_url)
    if continue_pull:
        return _continue_pull(root, state)
    fetched = ApiClient(state["api_url"]).json(
        "/v1/fetch", {"collection": state["name"]}
    )
    head = fetched["version"]["version_id"]
    cache_manifest(root, head, fetched["manifest"])
    base_id = state.get("base_version_id")
    base = load_cached_manifest(root, base_id) if base_id else None
    local = local_manifest(root, state)
    comparison_base = comparison_manifest(base, state)
    comparison_remote = comparison_manifest(fetched["manifest"], state)
    local_changes = changed_keys(comparison_base, local)
    remote_changes = changed_keys(comparison_base, comparison_remote)
    update_remote(root, head_version_id=head)
    if local_changes and remote_changes:
        _record_conflict(
            root,
            base_id,
            head,
            comparison_base,
            local,
            comparison_remote,
            local_changes,
            remote_changes,
        )
    if not remote_changes:
        return {
            "status": "ready",
            "name": state["name"],
            "version_id": base_id,
            "updated": False,
        }
    if state.get("kind") == "authoring":
        write_conflicts(
            root,
            {
                "base_version_id": base_id,
                "head_version_id": head,
                "conflicts": [
                    f"{kind}:{value}" for kind, value in sorted(remote_changes)
                ],
                "local_changes": manifest_changes(comparison_base, local),
                "remote_changes": manifest_changes(comparison_base, comparison_remote),
            },
        )
        raise ReIndexError(
            "Remote advanced; authoring worktree was not replaced. Reconcile "
            "locally, then run pull --continue"
        )
    return _checkout(state["name"], root, state["api_url"], head, replace=True)


def local_manifest(root: Path, state: dict) -> dict:
    if state.get("kind") == "authoring":
        return build_transport_manifest(resolve_collection(root))[0]
    node_dir = root / str(state["node_dir"])
    files = [
        {
            "namespace": "package",
            "logical_path": path.relative_to(node_dir).as_posix(),
            "sha256": sha256_file(path),
            "byte_size": path.stat().st_size,
            "media_type": "text/markdown",
        }
        for path in sorted(node_dir.rglob("*.node.md"))
    ]
    return {
        "spec": "reindex/transport@1.0",
        "package_root": node_dir.name,
        "files": files,
    }


def comparison_manifest(manifest: dict | None, state: dict) -> dict | None:
    if manifest is None or state.get("kind") != "node-checkout":
        return manifest
    return {
        **manifest,
        "files": [
            item
            for item in manifest.get("files", [])
            if item["namespace"] == "package"
            and item["logical_path"].endswith(".node.md")
        ],
    }


def _continue_pull(root: Path, state: dict) -> dict:
    conflict = load_conflicts(root)
    if not conflict:
        raise ReIndexError("No local conflict is awaiting resolution")
    head = conflict["head_version_id"]
    clear_conflicts(root)
    update_remote(root, base_version_id=head, head_version_id=head)
    return {"status": "ready", "name": state["name"], "base_version_id": head}


def _record_conflict(root, base_id, head, base, local, remote, local_keys, remote_keys):
    conflicts = sorted(local_keys & remote_keys) or sorted(local_keys | remote_keys)
    write_conflicts(
        root,
        {
            "base_version_id": base_id,
            "head_version_id": head,
            "conflicts": [f"{kind}:{value}" for kind, value in conflicts],
            "local_changes": manifest_changes(base, local),
            "remote_changes": manifest_changes(base, remote),
        },
    )
    raise ReIndexError(
        "Local and remote changes conflict; resolve locally, then run pull --continue"
    )


def _checkout(
    name: str,
    destination: Path,
    url: str,
    version_id: str | None,
    *,
    replace: bool,
) -> dict:
    payload = {"collection": name}
    if version_id:
        payload["version_id"] = version_id
    content, headers = ApiClient(url).bytes("/v1/pull", payload)
    if destination.exists() and any(destination.iterdir()) and not replace:
        raise ReIndexError(f"Pull destination is not empty: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent)
    )
    try:
        node_dir = staging / "reIndex" / name
        count = extract_node_archive(content, node_dir)
        resolved_version = _header(headers, "x-reindex-version-id")
        fetched = ApiClient(url).json(
            "/v1/fetch", {"collection": name, "version_id": resolved_version}
        )
        cache_manifest(staging, resolved_version, fetched["manifest"])
        write_remote(
            staging,
            {
                "name": name,
                "collection_id": fetched["collection_id"],
                "api_url": url,
                "package_hash": _header(headers, "x-reindex-package-hash"),
                "base_version_id": resolved_version,
                "head_version_id": resolved_version,
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
        "version_id": resolved_version,
        "package_hash": _header(headers, "x-reindex-package-hash"),
    }


def _header(headers: dict[str, str], name: str) -> str | None:
    return next((value for key, value in headers.items() if key.lower() == name), None)
