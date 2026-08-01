from __future__ import annotations

from reindex_cli.errors import ManifestError
from reindex_cli.manifest.models import InputManifest
from reindex_cli.parsers.profiles import csv_profile, pdf_profile
from reindex_cli.pipeline.models import SourceItem


def input_changes(
    manifest: InputManifest,
    discovered: dict[str, SourceItem],
    selected: set[str],
    previous: dict,
) -> dict:
    old_hashes = previous.get("item_hashes", {}) if isinstance(previous, dict) else {}
    old_paths = (
        set(previous.get("item_paths", [])) if isinstance(previous, dict) else set()
    )
    return {
        "manifest_changed": manifest.sha256 != previous.get("manifest_sha256"),
        "new_inputs": sorted(selected - old_paths),
        "changed_inputs": sorted(
            path
            for path in selected & old_paths
            if old_hashes.get(path) != discovered[path].sha256
        ),
        "removed_inputs": sorted(old_paths - selected),
    }


def has_input_changes(changes: dict) -> bool:
    return bool(
        changes["manifest_changed"]
        or changes["new_inputs"]
        or changes["changed_inputs"]
        or changes["removed_inputs"]
    )


def inspect_items(
    manifest: InputManifest,
    discovered: dict[str, SourceItem],
    selected: set[str],
    previous: dict,
) -> tuple[list[dict], list[dict]]:
    old_hashes = previous.get("item_hashes", {}) if isinstance(previous, dict) else {}
    profiles: dict[str, dict] = {}
    items = []
    for relative in sorted(selected):
        item = discovered[relative]
        profile = _profile(item, profiles)
        relation = _relation(item, discovered, profiles)
        previous_hash = old_hashes.get(relative)
        change = (
            "new"
            if previous_hash is None
            else "changed"
            if previous_hash != item.sha256
            else "unchanged"
        )
        items.append(
            {
                "path": relative,
                "media_type": item.media_type,
                "sha256": item.sha256,
                "byte_size": item.path.stat().st_size,
                "parse": item.config.parse,
                "relation": relation,
                "profile": profile,
                "change": change,
            }
        )
    ignored = [
        {"path": path, "reason": "manifest"}
        for path, config in sorted(manifest.items.items())
        if config.ignore
    ]
    return items, ignored


def _profile(item: SourceItem, profiles: dict[str, dict]) -> dict | None:
    if item.relative in profiles:
        return profiles[item.relative]
    suffix = item.path.suffix.lower()
    if suffix == ".csv":
        value = csv_profile(item.path, item.relative)
    elif suffix == ".pdf":
        value = pdf_profile(item.path, item.relative)
    else:
        value = None
    if value is not None:
        profiles[item.relative] = value
    return value


def _relation(
    item: SourceItem,
    discovered: dict[str, SourceItem],
    profiles: dict[str, dict],
) -> dict | None:
    target = item.config.part_of or item.config.derived_from
    if not target:
        return None
    relation = {
        "type": "part_of" if item.config.part_of else "derived_from",
        "target": target,
        "target_valid": target in discovered,
    }
    if item.config.pages:
        target_profile = _profile(discovered[target], profiles)
        page_count = target_profile.get("page_count") if target_profile else None
        pages_valid = bool(page_count and item.config.pages[1] <= page_count)
        relation.update(
            {
                "pages": list(item.config.pages),
                "target_page_count": page_count,
                "pages_valid": pages_valid,
            }
        )
        if not pages_valid:
            raise ManifestError(
                f"pages exceed relation target page count: {item.relative}"
            )
    return relation
