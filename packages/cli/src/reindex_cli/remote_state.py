from __future__ import annotations

from pathlib import Path

from reindex_cli.config import get_api_url
from reindex_cli.errors import ReIndexError
from reindex_cli.util import atomic_json, load_json


def write_remote(root: Path, value: dict) -> None:
    atomic_json(root / ".rei" / "remote.json", {"spec": "reindex/remote@1.0", **value})


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
            if isinstance(value, dict) and value.get("spec") == "reindex/remote@1.0":
                return candidate, value
            raise ReIndexError(f"Invalid remote state: {path}")
    return None, None
