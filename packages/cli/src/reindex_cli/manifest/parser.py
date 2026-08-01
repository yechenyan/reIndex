from __future__ import annotations

import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from reindex_cli.errors import ManifestError
from reindex_cli.manifest.models import InputManifest, ItemConfig
from reindex_cli.manifest.yaml_support import load_restricted_yaml
from reindex_cli.util import sha256_bytes

TOP_FIELDS = {"spec", "collection", "items"}
ITEM_FIELDS = {
    "parse",
    "origin_url",
    "part_of",
    "derived_from",
    "pages",
    "title",
    "description",
    "quality",
    "ignore",
}
RESERVED = {"reIndex", ".rei", ".git", "__pycache__"}


def load_manifest(root: Path) -> InputManifest:
    path = root / "reIndex.md"
    title = root.name
    default_description = f'Collection imported from "{title}".'
    if not path.is_file():
        return InputManifest(None, None, title, default_description, {})
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ManifestError("reIndex.md must be UTF-8") from error
    if "\r" in text:
        raise ManifestError("reIndex.md must use LF line endings")
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0] != "":
        raise ManifestError("reIndex.md must start with YAML frontmatter")
    value = load_restricted_yaml(parts[1], "reIndex.md")
    if not isinstance(value, dict) or value.get("spec") != "reindex/input@1.0":
        raise ManifestError("reIndex.md must declare spec: reindex/input@1.0")
    _unknown(value, TOP_FIELDS, "top-level")
    collection = value.get("collection", {})
    if not isinstance(collection, dict) or set(collection) - {"title", "description"}:
        raise ManifestError("collection must contain only title and description")
    title = _optional_text(collection.get("title"), "collection.title") or title
    description = (
        _optional_text(collection.get("description"), "collection.description")
        or default_description
    )
    items = _parse_items(root, value.get("items", {}))
    _validate_relations(items)
    return InputManifest(
        path, sha256_bytes(raw), title, description, items, parts[2].lstrip("\n")
    )


def _parse_items(root: Path, raw: object) -> dict[str, ItemConfig]:
    if not isinstance(raw, dict):
        raise ManifestError("items must be a mapping")
    result: dict[str, ItemConfig] = {}
    for key, value in raw.items():
        path = _safe_path(key)
        if not isinstance(value, dict):
            raise ManifestError(f"item must be a mapping: {path}")
        _unknown(value, ITEM_FIELDS, f"item {path}")
        if not (root / path).exists():
            raise ManifestError(f"manifest item does not exist: {path}")
        if (root / path).is_symlink():
            raise ManifestError(f"manifest items cannot be symlinks: {path}")
        if (root / path).is_dir() and set(value) - {
            "title",
            "description",
            "ignore",
        }:
            raise ManifestError(
                f"directory items allow only title, description and ignore: {path}"
            )
        ignore = value.get("ignore", False)
        if not isinstance(ignore, bool):
            raise ManifestError(f"ignore must be boolean: {path}")
        if ignore and len(value) != 1:
            raise ManifestError(f"ignore cannot be combined with other fields: {path}")
        relation = value.get("part_of"), value.get("derived_from")
        if all(relation):
            raise ManifestError(
                f"part_of and derived_from are mutually exclusive: {path}"
            )
        pages = _pages(value.get("pages"), path)
        if pages and not any(relation):
            raise ManifestError(f"pages requires part_of or derived_from: {path}")
        quality = _quality(value.get("quality"), path)
        if quality and (root / path).suffix.lower() != ".csv":
            raise ManifestError(f"quality is supported only for CSV items: {path}")
        origin_url = _optional_text(value.get("origin_url"), f"{path}.origin_url")
        if origin_url and urlparse(origin_url).scheme not in {"http", "https"}:
            raise ManifestError(f"origin_url must use HTTP(S): {path}")
        result[path] = ItemConfig(
            path=path,
            parse=_parse_policy(value.get("parse"), path),
            title=_optional_text(value.get("title"), f"{path}.title"),
            description=_optional_text(value.get("description"), f"{path}.description"),
            origin_url=origin_url,
            part_of=_safe_path(relation[0]) if relation[0] else None,
            derived_from=_safe_path(relation[1]) if relation[1] else None,
            pages=pages,
            quality=quality,
            ignore=ignore,
        )
    return result


def _parse_policy(value: object, path: str) -> dict[str, str]:
    result = {"text": "auto", "images": "auto", "tables": "auto"}
    if value is None or value == "auto":
        return result
    if not isinstance(value, dict) or set(value) - set(result):
        raise ManifestError(f"invalid parse policy: {path}")
    for key, setting in value.items():
        if setting not in {"auto", "off"}:
            raise ManifestError(f"parse values are auto or off: {path}.{key}")
        result[key] = setting
    return result


def _validate_relations(items: dict[str, ItemConfig]) -> None:
    for path, item in items.items():
        target = item.part_of or item.derived_from
        if target and target == path:
            raise ManifestError(f"item cannot reference itself: {path}")
        if target and target in items and items[target].ignore:
            raise ManifestError(f"relation target is ignored: {target}")
    for start in items:
        seen: set[str] = set()
        current = start
        while current in items:
            if current in seen:
                raise ManifestError(f"relation cycle includes: {current}")
            seen.add(current)
            item = items[current]
            current = item.part_of or item.derived_from or ""


def _safe_path(value: object) -> str:
    if not isinstance(value, str):
        raise ManifestError("item paths must be strings")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} or part in RESERVED for part in path.parts)
    ):
        raise ManifestError(f"unsafe item path: {value}")
    if "\\" in value or path.as_posix() != value:
        raise ManifestError(f"item path must be canonical POSIX: {value}")
    if unicodedata.normalize("NFC", value) != value:
        raise ManifestError(f"item path must use Unicode NFC: {value}")
    return value


def _pages(value: object, path: str) -> tuple[int, int] | None:
    if value is None:
        return None
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(not isinstance(v, int) or isinstance(v, bool) or v < 1 for v in value)
    ):
        raise ManifestError(f"pages must be two positive integers: {path}")
    if value[0] > value[1]:
        raise ManifestError(f"pages must be ascending: {path}")
    return value[0], value[1]


def _quality(value: object, path: str) -> dict[str, Any] | None:
    if value is None:
        return None
    allowed = {"expected_rows", "expected_columns", "primary_key"}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ManifestError(f"invalid quality fields: {path}")
    if "expected_rows" in value and (
        not isinstance(value["expected_rows"], int)
        or isinstance(value["expected_rows"], bool)
        or value["expected_rows"] < 0
    ):
        raise ManifestError(f"invalid expected_rows: {path}")
    for key in ("expected_columns", "primary_key"):
        if key in value and (
            not isinstance(value[key], list)
            or any(not isinstance(v, str) or not v for v in value[key])
        ):
            raise ManifestError(f"invalid {key}: {path}")
    return dict(value)


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{field} must be a non-empty string")
    return value.strip()


def _unknown(value: dict, allowed: set[str], where: str) -> None:
    if unknown := set(value) - allowed:
        raise ManifestError(f"unknown {where} fields: {', '.join(sorted(unknown))}")
