from __future__ import annotations

from pathlib import Path

from reindex_cli.errors import ManifestError
from reindex_cli.manifest.models import InputManifest
from reindex_cli.pipeline.models import SourceItem


def active_paths(
    root: Path,
    scope_relative: str,
    discovered: dict[str, SourceItem],
    previous: dict,
    manifest: InputManifest,
) -> set[str]:
    if scope_relative == ".":
        selected = set(discovered)
    else:
        scope = scope_relative.rstrip("/")
        selected = {
            path for path in discovered if path == scope or path.startswith(scope + "/")
        }
        selected |= set(previous.get("item_paths", [])) & set(discovered)
    changed = True
    while changed:
        changed = False
        for path, item in manifest.items.items():
            target = item.part_of or item.derived_from
            if not target:
                continue
            if target not in discovered:
                raise ManifestError(f"relation target cannot be discovered: {target}")
            if not discovered[target].path.is_file():
                raise ManifestError(f"relation target must be a file: {target}")
            if item.pages and discovered[target].path.suffix.lower() != ".pdf":
                raise ManifestError(f"pages require a paginated PDF target: {path}")
            if path in selected or target in selected:
                before = len(selected)
                selected.update({path, target})
                changed = changed or len(selected) != before
    return selected


def external_table_pages(pdf_path: str, discovered: dict[str, SourceItem]) -> set[int]:
    pages: set[int] = set()
    for item in discovered.values():
        if (
            item.config.part_of == pdf_path
            and item.path.suffix.lower() == ".csv"
            and item.config.pages
        ):
            pages.update(range(item.config.pages[0], item.config.pages[1] + 1))
    return pages
