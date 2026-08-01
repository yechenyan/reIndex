from __future__ import annotations

import hashlib
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
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
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
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open("rb") as incoming, target.open("wb") as output:
                while chunk := incoming.read(1024 * 1024):
                    output.write(chunk)
        return StoredObject(digest.hexdigest(), size, key)

    def open(self, object_key: str) -> BinaryIO:
        return (self.root / object_key).open("rb")

    @contextmanager
    def materialize(self, object_key: str) -> Iterator[Path]:
        yield self.root / object_key
