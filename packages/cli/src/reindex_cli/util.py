from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Any


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def slugify(value: str, fallback: str = "node") -> str:
    value = value.replace("ß", "ss")
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug[:60].rstrip("-") or fallback


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
