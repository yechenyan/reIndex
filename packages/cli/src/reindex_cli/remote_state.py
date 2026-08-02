from __future__ import annotations

import re
from pathlib import Path

from reindex_cli.config import get_api_url
from reindex_cli.errors import ReIndexError
from reindex_cli.util import atomic_json, load_json

REMOTE_SPEC = "reindex/remote@2.0"
CONFLICT_SPEC = "reindex/conflicts@1.0"


def write_remote(root: Path, value: dict) -> None:
    atomic_json(root / ".rei" / "remote.json", {"spec": REMOTE_SPEC, **value})


def update_remote(root: Path, **changes) -> dict:
    state = _load_remote(root)
    state.update(changes)
    payload = {key: value for key, value in state.items() if key != "spec"}
    write_remote(root, payload)
    return {"spec": REMOTE_SPEC, **payload}


def cache_manifest(root: Path, version_id: str, manifest: dict) -> Path:
    path = manifest_cache_path(root, version_id)
    atomic_json(path, manifest)
    return path


def load_cached_manifest(root: Path, version_id: str) -> dict | None:
    value = load_json(manifest_cache_path(root, version_id), None)
    if value is not None and not isinstance(value, dict):
        raise ReIndexError(f"Invalid cached manifest for version: {version_id}")
    return value


def manifest_cache_path(root: Path, version_id: str) -> Path:
    return (
        root
        / ".rei"
        / "cache"
        / "remote"
        / "versions"
        / _safe_id(version_id)
        / "manifest.json"
    )


def conflict_path(root: Path) -> Path:
    return root / ".rei" / "conflicts.json"


def write_conflicts(root: Path, value: dict) -> Path:
    path = conflict_path(root)
    atomic_json(path, {"spec": CONFLICT_SPEC, **value})
    return path


def load_conflicts(root: Path) -> dict | None:
    path = conflict_path(root)
    value = load_json(path, None)
    if value is None:
        return None
    if not isinstance(value, dict) or value.get("spec") != CONFLICT_SPEC:
        raise ReIndexError(f"Invalid conflict state: {path}")
    return value


def clear_conflicts(root: Path) -> None:
    conflict_path(root).unlink(missing_ok=True)


def resolve_remote(
    start: Path, explicit_name: str | None = None, explicit_url: str | None = None
) -> tuple[Path, dict]:
    root, state = _find_remote(start)
    if state is None and explicit_name is None:
        raise ReIndexError("No remote is configured; run rei push/pull or use --remote")
    value = dict(state or {})
    if explicit_name:
        value["name"] = explicit_name
    if not isinstance(value.get("name"), str):
        raise ReIndexError("Remote Collection name is missing")
    value["api_url"] = get_api_url(explicit_url or value.get("api_url"))
    return root or start.resolve(), value


def _find_remote(start: Path) -> tuple[Path | None, dict | None]:
    requested = start.expanduser().resolve()
    current = requested if requested.is_dir() else requested.parent
    for candidate in (current, *current.parents):
        path = candidate / ".rei" / "remote.json"
        if path.is_file():
            value = load_json(path, None)
            if isinstance(value, dict) and value.get("spec") == REMOTE_SPEC:
                return candidate, value
            raise ReIndexError(f"Invalid remote state: {path}")
    return None, None


def _load_remote(root: Path) -> dict:
    path = root / ".rei" / "remote.json"
    value = load_json(path, None)
    if not isinstance(value, dict) or value.get("spec") != REMOTE_SPEC:
        raise ReIndexError(f"Invalid remote state: {path}")
    return value


def _safe_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value) or ".." in value:
        raise ReIndexError(f"Invalid version ID: {value}")
    return value
