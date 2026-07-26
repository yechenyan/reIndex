from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from fastapi import UploadFile

from reindex_server.domain import safe_relative_path


class FileStore:
    """Development object storage adapter; production can replace this with S3."""

    def __init__(self, root: Path) -> None:
        self.root = root

    async def save_raw(self, collection_id: str, raw_path: str, upload: UploadFile) -> tuple[str, Path]:
        target = self.root / "collections" / collection_id / "raw" / safe_relative_path(raw_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with target.open("wb") as stream:
            while chunk := await upload.read(1024 * 1024):
                digest.update(chunk)
                stream.write(chunk)
        return digest.hexdigest(), target

    def raw_file(self, collection_id: str, raw_path: str) -> Path:
        return self.root / "collections" / collection_id / "raw" / safe_relative_path(raw_path)

    def copy_resource(self, collection_id: str, revision_id: str, source: Path, relative_path: str) -> str:
        key = Path("collections") / collection_id / "revisions" / revision_id / safe_relative_path(relative_path)
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return str(key)

    def resource_file(self, key: str) -> Path:
        return self.root / safe_relative_path(key)
