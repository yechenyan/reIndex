from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import yaml
from yaml.tokens import AliasToken, AnchorToken, DirectiveToken, TagToken


class PackageError(ValueError):
    pass


class _UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise PackageError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


@dataclass(frozen=True)
class ParsedCard:
    metadata: dict
    markdown: str
    content: bytes


def parse_node_card(content: bytes | str, relative: str) -> ParsedCard:
    raw = content.encode() if isinstance(content, str) else content
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PackageError(f"Node card is not UTF-8: {relative}") from error
    if "\r" in text:
        raise PackageError(f"Node card must use LF line endings: {relative}")
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0] != "":
        raise PackageError(f"invalid frontmatter: {relative}")
    try:
        tokens = yaml.scan(parts[1])
        if any(
            isinstance(token, (AliasToken, AnchorToken, DirectiveToken, TagToken))
            for token in tokens
        ):
            raise PackageError(f"unsupported YAML feature: {relative}")
        metadata = yaml.load(parts[1], Loader=_UniqueLoader)
    except yaml.YAMLError as error:
        raise PackageError(f"invalid YAML: {relative}") from error
    _validate_metadata(metadata, relative)
    return ParsedCard(metadata, parts[2].lstrip("\n"), raw)


def _validate_metadata(metadata: object, relative: str) -> None:
    required = {"spec", "id", "kind", "title", "description"}
    if not isinstance(metadata, dict) or not required <= metadata.keys():
        raise PackageError(f"missing Node metadata: {relative}")
    if metadata["spec"] != "reindex/node@1.0":
        raise PackageError(f"unsupported Node spec: {relative}")
    try:
        UUID(str(metadata["id"]))
    except ValueError as error:
        raise PackageError(f"invalid Node UUID: {relative}") from error
    if metadata["kind"] not in {"group", "text", "table", "image", "file"}:
        raise PackageError(f"invalid Node kind: {relative}")
    if not all(
        isinstance(metadata[key], str) and metadata[key].strip()
        for key in ("title", "description")
    ):
        raise PackageError(f"title and description are required: {relative}")
    if metadata["kind"] == "group" and "content" in metadata:
        raise PackageError(f"group Node cannot have content: {relative}")
    if metadata["kind"] != "group" and "content" not in metadata:
        raise PackageError(f"non-group Node requires content: {relative}")
    _validate_file_ref(metadata.get("source"), relative, source=True)
    _validate_file_ref(
        metadata.get("content"), relative, required=metadata["kind"] != "group"
    )
    assets = metadata.get("assets", [])
    if not isinstance(assets, list):
        raise PackageError(f"assets must be a list: {relative}")
    for asset in assets:
        _validate_file_ref(asset, relative, asset=True, required=True)


def _validate_file_ref(
    value, relative: str, *, source=False, asset=False, required=False
) -> None:
    if value is None and not required:
        return
    if not isinstance(value, dict) or not isinstance(value.get("uri"), str):
        raise PackageError(f"invalid resource reference: {relative}")
    if not isinstance(value.get("sha256"), str) or len(value["sha256"]) != 64:
        raise PackageError(f"invalid resource SHA-256: {relative}")
    if source and not value["uri"].startswith("raw://"):
        raise PackageError(f"source must use raw://: {relative}")
    if not source and not (
        value["uri"].startswith("./") or value["uri"].startswith("raw://")
    ):
        raise PackageError(f"content and assets must use ./ or raw://: {relative}")
    if not source and not isinstance(value.get("media_type"), str):
        raise PackageError(f"media_type is required: {relative}")
    if asset and not all(
        isinstance(value.get(key), str) and value[key]
        for key in ("role", "description")
    ):
        raise PackageError(f"asset role and description are required: {relative}")
