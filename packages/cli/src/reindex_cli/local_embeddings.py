from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath

from reindex_cli.errors import ReIndexError
from reindex_cli.package.cards import parse_card
from reindex_cli.parsers.nap_hybrid import split_markdown_section

PROFILE = "qwen3-embedding-0.6b@1024"
MODEL = "Qwen/Qwen3-Embedding-0.6B"


def local_embeddings(package: Path, raw_root: Path) -> dict | None:
    setting = os.environ.get("REINDEX_LOCAL_EMBEDDINGS", "auto").lower()
    if setting == "disabled":
        return None
    if setting not in {"auto", "qwen"}:
        raise ReIndexError("REINDEX_LOCAL_EMBEDDINGS must be auto, qwen, or disabled")
    texts = _search_texts(package, raw_root)
    unique = {hashlib.sha256(text.encode()).hexdigest(): text for text in texts}
    if not unique:
        return None
    cached = _load_cache(raw_root)
    missing = [key for key in unique if key not in cached]
    if missing:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            if setting == "qwen":
                raise ReIndexError(
                    "Install reindex[embeddings] to generate missing local embeddings"
                ) from error
            return None
        try:
            device, batch_size = _embedding_options()
            model = SentenceTransformer(
                MODEL, trust_remote_code=True, local_files_only=True, device=device
            )
        except Exception as error:
            if setting == "qwen":
                raise ReIndexError(
                    f"Local embedding model is unavailable: {error}"
                ) from error
            return None
        vectors = model.encode(
            [unique[key] for key in missing],
            normalize_embeddings=True,
            batch_size=batch_size,
        ).tolist()
        cached.update(zip(missing, vectors, strict=True))
    result = {key: cached[key] for key in unique}
    _write_cache(raw_root, result)
    return {"profile": PROFILE, "vectors": result}


def _cache_path(raw_root: Path) -> Path:
    return raw_root / ".rei" / "cache" / "embeddings" / f"{PROFILE}.json"


def _load_cache(raw_root: Path) -> dict[str, list[float]]:
    try:
        value = json.loads(_cache_path(raw_root).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_cache(raw_root: Path, vectors: dict[str, list[float]]) -> None:
    path = _cache_path(raw_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(vectors, separators=(",", ":")), encoding="utf-8")


def _embedding_options() -> tuple[str | None, int]:
    default_device = "mps" if sys.platform == "darwin" else "auto"
    device = os.environ.get("REINDEX_LOCAL_EMBEDDING_DEVICE", default_device).lower()
    if device not in {"auto", "cpu", "cuda", "mps"}:
        raise ReIndexError(
            "REINDEX_LOCAL_EMBEDDING_DEVICE must be auto, cpu, cuda, or mps"
        )
    try:
        batch_size = int(os.environ.get("REINDEX_LOCAL_EMBEDDING_BATCH_SIZE", "2"))
    except ValueError as error:
        raise ReIndexError("REINDEX_LOCAL_EMBEDDING_BATCH_SIZE must be an integer") from error
    if batch_size < 1:
        raise ReIndexError("REINDEX_LOCAL_EMBEDDING_BATCH_SIZE must be positive")
    return (None if device == "auto" else device), batch_size


def _search_texts(package: Path, raw_root: Path) -> list[str]:
    values: list[str] = []
    for path in sorted(package.rglob("*.node.md")):
        metadata, body = parse_card(path)
        values.extend(_contextual(metadata, body))
        content = metadata.get("content")
        if not content:
            continue
        file = _content_path(package, raw_root, path, content["uri"])
        media_type = content["media_type"].split(";", 1)[0]
        if metadata["kind"] == "table":
            with file.open(encoding="utf-8", newline="") as stream:
                for row in csv.DictReader(stream):
                    text = " | ".join(f"{key}: {value}" for key, value in row.items())
                    values.extend(_contextual(metadata, text))
        elif media_type in {"text/markdown", "text/plain"}:
            text = file.read_text(encoding="utf-8")
            chunks = split_markdown_section(text) if metadata["kind"] == "text" else None
            values.extend(
                _contextual_one(metadata, chunk) for chunk in (chunks or [item[0] for item in _chunks(text)])
            )
    return values


def _content_path(package: Path, raw_root: Path, card: Path, uri: str) -> Path:
    if uri.startswith("raw://"):
        return raw_root / uri.removeprefix("raw://")
    return package / PurePosixPath(card.relative_to(package).parent, uri.removeprefix("./"))


def _contextual(metadata: dict, text: str) -> list[str]:
    return [_contextual_one(metadata, chunk) for chunk, _start, _end in _chunks(text)]


def _contextual_one(metadata: dict, text: str) -> str:
    return f"{metadata['title']}\n{metadata['description']}\n{text}"


def _chunks(body: str, target_tokens: int = 600, overlap_tokens: int = 80):
    lines = body.splitlines()
    if not lines:
        return [("", 1, 1)]
    blocks, current, start = [], [], 1
    for number, line in enumerate(lines, 1):
        if not line.strip() and current:
            blocks.append((current, start, number - 1))
            current = []
        else:
            if not current:
                start = number
            current.append(line)
    if current:
        blocks.append((current, start, len(lines)))
    chunks, pending, count = [], [], 0
    for block in blocks:
        block_count = len(re.findall(r"\S+", "\n".join(block[0])))
        if pending and count + block_count > target_tokens:
            chunks.append(_join(pending))
            pending, count = _overlap(pending, overlap_tokens)
        pending.append(block)
        count += block_count
    if pending:
        chunks.append(_join(pending))
    return chunks


def _join(blocks):
    return ("\n\n".join("\n".join(block[0]) for block in blocks), blocks[0][1], blocks[-1][2])


def _overlap(blocks, target):
    result, count = [], 0
    for block in reversed(blocks):
        result.insert(0, block)
        count += len(re.findall(r"\S+", "\n".join(block[0])))
        if count >= target:
            break
    return result, count
