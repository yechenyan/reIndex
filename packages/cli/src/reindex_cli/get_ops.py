from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from reindex_cli.api import ApiClient
from reindex_cli.config import cache_dir
from reindex_cli.errors import ReIndexError
from reindex_cli.package.cards import parse_card
from reindex_cli.remote_state import resolve_remote
from reindex_cli.util import sha256_file


@dataclass(frozen=True)
class LocalResource:
    path: Path | None
    sha256: str | None
    target: str
    payload: dict


def get_resource(
    reference: str,
    start: Path,
    *,
    target: str | None,
    asset_ordinal: int | None,
    output: Path | None,
    remote: str | None,
    api_url: str | None,
) -> dict:
    root, state = resolve_remote(start, remote, api_url)
    resource = _local_resource(root, state, reference, target, asset_ordinal)
    selected = _healthy(resource.path, resource.sha256)
    source = "local"
    if selected is None and resource.sha256:
        selected = _healthy(_cache_path(resource.sha256), resource.sha256)
        source = "cache"
    if selected is None:
        content, headers = ApiClient(state["api_url"]).bytes(
            "/v1/get", {"collection": state["name"], **resource.payload}
        )
        server_hash = _header(headers, "x-reindex-sha256")
        if not server_hash:
            raise ReIndexError("Server get response did not include SHA-256")
        cache = _cache_path(server_hash)
        cache.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache.with_name(f".{cache.name}.tmp")
        temporary.write_bytes(content)
        if sha256_file(temporary) != server_hash:
            temporary.unlink(missing_ok=True)
            raise ReIndexError("Downloaded resource SHA-256 mismatch")
        if resource.sha256 and resource.sha256 != server_hash:
            temporary.unlink(missing_ok=True)
            raise ReIndexError("Remote resource differs from Node metadata")
        temporary.replace(cache)
        selected = cache
        source = "download"
    final = _materialize(selected, output)
    return {
        "status": "ready",
        "name": state["name"],
        "reference": reference,
        "target": resource.target,
        "source": source,
        "path": str(final),
        "sha256": sha256_file(final),
    }


def _local_resource(root, state, reference, target, asset_ordinal):
    if reference.startswith("raw://"):
        relative = _safe(reference.removeprefix("raw://"))
        digest = _raw_hash(root, state, reference)
        return LocalResource(
            root / relative,
            digest,
            "raw",
            {"raw_uri": reference},
        )
    node_dir = root / str(state.get("node_dir", ""))
    node_path = _safe(reference)
    card_path = node_dir / node_path
    if not card_path.is_file():
        return LocalResource(
            None,
            None,
            target or "content",
            _node_payload(node_path, target or "content", asset_ordinal),
        )
    metadata, _body = parse_card(card_path)
    resolved_target = target or ("card" if metadata["kind"] == "group" else "content")
    if resolved_target == "card":
        return LocalResource(
            card_path,
            sha256_file(card_path),
            "card",
            _node_payload(node_path, "card", asset_ordinal),
        )
    value = _reference(metadata, resolved_target, asset_ordinal)
    uri = str(value["uri"])
    path = (
        root / _safe(uri.removeprefix("raw://"))
        if uri.startswith("raw://")
        else card_path.parent / _safe(uri.removeprefix("./"))
    )
    return LocalResource(
        path,
        str(value["sha256"]),
        resolved_target,
        _node_payload(node_path, resolved_target, asset_ordinal),
    )


def _reference(metadata, target, ordinal):
    if target in {"source", "content"}:
        value = metadata.get(target)
    elif target == "asset":
        assets = metadata.get("assets", [])
        value = assets[(ordinal or 1) - 1] if len(assets) >= (ordinal or 1) else None
    else:
        value = None
    if not isinstance(value, dict):
        raise ReIndexError(f"Node has no {target} resource")
    return value


def _raw_hash(root, state, uri):
    node_dir = root / str(state.get("node_dir", ""))
    for card in node_dir.rglob("*.node.md") if node_dir.is_dir() else ():
        metadata, _body = parse_card(card)
        for value in [
            metadata.get("source"),
            metadata.get("content"),
            *metadata.get("assets", []),
        ]:
            if isinstance(value, dict) and value.get("uri") == uri:
                return str(value["sha256"])
    return None


def _node_payload(path, target, ordinal):
    value = {"node_path": path, "target": target}
    if target == "asset":
        value["asset_ordinal"] = ordinal or 1
    return value


def _cache_path(digest: str) -> Path:
    return cache_dir() / "objects" / "sha256" / digest[:2] / digest[2:4] / digest


def _healthy(path: Path | None, digest: str | None) -> Path | None:
    if path is None or not path.is_file():
        return None
    if digest is None or sha256_file(path) == digest:
        return path
    return None


def _materialize(source: Path, output: Path | None) -> Path:
    if output is None:
        return source
    target = output.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if sha256_file(target) == sha256_file(source):
            return target
        raise ReIndexError(f"Output already exists with different content: {target}")
    shutil.copy2(source, target)
    return target


def _safe(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ReIndexError(f"Unsafe resource path: {value}")
    return path.as_posix()


def _header(headers, name):
    return next((value for key, value in headers.items() if key.lower() == name), None)
