from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class StoredObject:
    sha256: str
    byte_size: int
    object_key: str


class ObjectStore(Protocol):
    def put_bytes(self, content: bytes) -> StoredObject: ...
    def put_file(self, source: Path) -> StoredObject: ...
    def open(self, object_key: str) -> BinaryIO: ...
    def materialize(self, object_key: str) -> AbstractContextManager[Path]: ...
    def exists(self, sha256: str) -> bool: ...
    def size(self, sha256: str) -> int | None: ...
    def sweep(self, retained_sha256: set[str], grace_seconds: int) -> int: ...


def object_key(sha256: str, prefix: str = "objects") -> str:
    return f"{prefix.strip('/')}/sha256/{sha256[:2]}/{sha256[2:4]}/{sha256}"


class FileStore:
    """Content-addressed local resource storage."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def put_bytes(self, content: bytes) -> StoredObject:
        digest = hashlib.sha256(content).hexdigest()
        key = object_key(digest)
        target = self.root / key
        if not target.is_file() or target.stat().st_size != len(content):
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = _temporary_path(target)
            try:
                temporary.write_bytes(content)
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        return StoredObject(digest, len(content), key)

    def put_file(self, source: Path) -> StoredObject:
        digest = hashlib.sha256()
        size = 0
        with source.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
        key = object_key(digest.hexdigest())
        target = self.root / key
        if not target.is_file() or target.stat().st_size != size:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = _temporary_path(target)
            try:
                with source.open("rb") as incoming, temporary.open("wb") as output:
                    while chunk := incoming.read(1024 * 1024):
                        output.write(chunk)
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        return StoredObject(digest.hexdigest(), size, key)

    def open(self, object_key: str) -> BinaryIO:
        return (self.root / object_key).open("rb")

    def exists(self, sha256: str) -> bool:
        return (self.root / object_key(sha256)).is_file()

    def size(self, sha256: str) -> int | None:
        path = self.root / object_key(sha256)
        return path.stat().st_size if path.is_file() else None

    def sweep(self, retained_sha256: set[str], grace_seconds: int) -> int:
        import time

        root = self.root / "objects" / "sha256"
        if not root.is_dir():
            return 0
        cutoff = time.time() - grace_seconds
        removed = 0
        for path in root.glob("*/*/*"):
            if (
                path.is_file()
                and path.name not in retained_sha256
                and path.stat().st_mtime < cutoff
            ):
                path.unlink()
                removed += 1
        return removed

    @contextmanager
    def materialize(self, object_key: str) -> Iterator[Path]:
        yield self.root / object_key


def _temporary_path(target: Path) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    os.close(descriptor)
    return Path(name)
