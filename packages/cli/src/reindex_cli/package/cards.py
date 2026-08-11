from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from reindex_cli.errors import PackageError
from reindex_cli.manifest.yaml_support import load_restricted_yaml
from reindex_cli.util import sha256_bytes


def render_card(metadata: dict[str, Any], body: str) -> bytes:
    frontmatter = yaml.safe_dump(
        metadata, allow_unicode=True, sort_keys=False, default_flow_style=False
    ).rstrip()
    return f"---\n{frontmatter}\n---\n{body.lstrip()}".encode()


def parse_card(path: Path) -> tuple[dict[str, Any], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise PackageError(f"Node card is not UTF-8: {path}") from error
    if "\r" in text:
        raise PackageError(f"Node card must use LF: {path}")
    if not text.startswith("---\n"):
        raise PackageError(f"invalid Node card frontmatter: {path}")
    try:
        frontmatter, body = text[4:].split("\n---\n", 1)
    except ValueError as error:
        raise PackageError(f"invalid Node card frontmatter: {path}") from error
    metadata = load_restricted_yaml(frontmatter, path.name)
    if not isinstance(metadata, dict):
        raise PackageError(f"Node metadata must be a mapping: {path}")
    return metadata, body.lstrip("\n")


def machine_hash(metadata: dict[str, Any]) -> str:
    value = json.dumps(
        metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256_bytes(value.encode())
