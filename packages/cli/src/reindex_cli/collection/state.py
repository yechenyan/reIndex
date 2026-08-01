from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from reindex_cli.errors import ReIndexError
from reindex_cli.util import atomic_json, load_json, slugify

COLLECTION_SPEC = "reindex/collection@1.0"


def create_collection(directory: Path) -> dict:
    root = directory.expanduser().resolve()
    if not root.is_dir():
        raise ReIndexError(f"Collection directory does not exist: {root}")
    state_path = root / ".rei" / "collection.json"
    if state_path.exists():
        return {**load_collection(root), "created": False}
    parent = _find_parent_collection(root.parent)
    if parent is not None:
        raise ReIndexError(f"Collection is nested inside existing Collection: {parent}")
    collection_id = str(uuid4())
    state = {
        "spec": COLLECTION_SPEC,
        "id": collection_id,
        "created_at": datetime.now(UTC).isoformat(),
        "output_dir": f"{collection_id}--{slugify(root.name, 'collection')}",
    }
    atomic_json(state_path, state)
    atomic_json(
        root / ".rei" / "identities.json",
        {"spec": "reindex/identities@1.0", "items": {}},
    )
    agent_path = root / ".rei" / "agent" / "collection.md"
    agent_path.parent.mkdir(parents=True, exist_ok=True)
    agent_path.write_text(
        f"# {root.name}\n\nCollection ID: `{collection_id}`.\n\n"
        "Review the root `reIndex.md` against real files before scanning.\n",
        encoding="utf-8",
        newline="\n",
    )
    return {**state, "created": True}


def load_collection(root: Path) -> dict:
    path = root / ".rei" / "collection.json"
    try:
        state = load_json(path, None)
    except (OSError, ValueError) as error:
        raise ReIndexError(f"Invalid Collection state: {path}") from error
    if not isinstance(state, dict) or state.get("spec") != COLLECTION_SPEC:
        raise ReIndexError(f"Unsupported Collection state: {path}")
    if not all(
        isinstance(state.get(key), str) and state[key] for key in ("id", "output_dir")
    ):
        raise ReIndexError(f"Incomplete Collection state: {path}")
    return state


def _find_parent_collection(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / ".rei" / "collection.json").is_file():
            return candidate
    return None
