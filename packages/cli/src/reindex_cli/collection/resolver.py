from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reindex_cli.collection.state import load_collection
from reindex_cli.errors import ReIndexError


@dataclass(frozen=True)
class CollectionContext:
    root: Path
    scope: Path
    scope_relative: str
    collection_id: str
    output_dir: Path
    state: dict


def resolve_collection(
    path: Path, explicit_root: Path | None = None
) -> CollectionContext:
    requested = path.expanduser().resolve()
    if not requested.exists():
        raise ReIndexError(f"Scan path does not exist: {requested}")
    root = (
        explicit_root.expanduser().resolve() if explicit_root else _find_root(requested)
    )
    if root is None:
        raise ReIndexError(f"No .rei/collection.json found above: {requested}")
    if not root.is_dir():
        raise ReIndexError(f"Collection root is not a directory: {root}")
    try:
        relative = requested.relative_to(root)
    except ValueError as error:
        raise ReIndexError(
            f"Scan path is outside Collection root: {requested}"
        ) from error
    state = load_collection(root)
    output = root / "reIndex" / state["output_dir"]
    return CollectionContext(
        root, requested, relative.as_posix(), state["id"], output, state
    )


def _find_root(requested: Path) -> Path | None:
    start = requested if requested.is_dir() else requested.parent
    for candidate in (start, *start.parents):
        if (candidate / ".rei" / "collection.json").is_file():
            return candidate
    return None
