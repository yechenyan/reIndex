from __future__ import annotations

import mimetypes
import unicodedata
from pathlib import Path

from reindex_cli.errors import ReIndexError
from reindex_cli.manifest.models import InputManifest, ItemConfig
from reindex_cli.pipeline.models import SourceItem
from reindex_cli.util import sha256_file

RESERVED = {"reIndex", ".rei", ".git", "__pycache__"}


def discover(root: Path, manifest: InputManifest) -> dict[str, SourceItem]:
    result: dict[str, SourceItem] = {}
    nap_runs = {
        path.parent
        for path in root.rglob("output.md")
        if "pdf-to-markdown" in path.parent.name
    }
    nap_source_dirs = {path.parent for path in nap_runs}
    explicit = set(manifest.items)
    explicit_hidden_dirs = {
        path
        for path in manifest.items
        if (root / path).is_dir()
        and any(part.startswith(".") for part in Path(path).parts)
    }
    ignored_dirs = {
        path
        for path, item in manifest.items.items()
        if item.ignore and (root / path).is_dir()
    }
    for path in sorted(
        root.rglob("*"),
        key=lambda item: unicodedata.normalize(
            "NFC", item.relative_to(root).as_posix()
        ).encode(),
    ):
        relative = path.relative_to(root).as_posix()
        if _reserved(path, root) or path.is_symlink() or not path.is_file():
            continue
        if any(run in path.parents for run in nap_runs) and path.parent not in nap_runs:
            continue
        if path.suffix.lower() == ".pdf" and path.parent in nap_source_dirs:
            continue
        if relative == "reIndex.md" or any(
            relative == item or relative.startswith(item + "/") for item in ignored_dirs
        ):
            continue
        hidden_allowed = relative in explicit or any(
            relative.startswith(directory + "/") for directory in explicit_hidden_dirs
        )
        if (
            any(part.startswith(".") for part in Path(relative).parts)
            and not hidden_allowed
        ):
            continue
        config = manifest.items.get(relative, ItemConfig(relative))
        if config.ignore:
            continue
        if not path.is_file():
            raise ReIndexError(f"Only regular files can be scanned: {relative}")
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        result[relative] = SourceItem(
            relative, path, sha256_file(path), media_type, config
        )
    for relative, config in manifest.items.items():
        path = root / relative
        if not config.ignore and path.is_file() and relative not in result:
            media_type = (
                mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            )
            result[relative] = SourceItem(
                relative, path, sha256_file(path), media_type, config
            )
    return result


def _reserved(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return any(part in RESERVED for part in relative.parts)
