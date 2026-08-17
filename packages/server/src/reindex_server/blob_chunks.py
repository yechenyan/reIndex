from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from reindex_server.errors import ConflictError
from reindex_server.version_serialization import unique_blobs


class ChunkedBlobUploadMixin:
    def upload_blob_chunk(
        self, upload_id: str, sha256: str, index: int, count: int, path: Path
    ) -> dict:
        session = self._session(upload_id)
        declared = unique_blobs(session.manifest).get(sha256)
        if declared is None:
            raise ValueError("blob is not declared by this upload session")
        if count < 1 or not 0 <= index < count:
            raise ValueError("invalid blob chunk position")
        previous = session.blob_chunk_counts.setdefault(sha256, count)
        if previous != count:
            raise ConflictError("blob chunk count differs within upload session")
        stored = self.store.put_file(path)
        session.blob_chunks.setdefault(sha256, {})[index] = (
            stored.object_key,
            stored.byte_size,
        )
        chunks = session.blob_chunks[sha256]
        if len(chunks) != count:
            return {"status": "partial", "received": len(chunks), "total": count}
        return self._assemble_blob(session, sha256, declared, chunks)

    def _assemble_blob(self, session, sha256: str, declared: dict, chunks: dict) -> dict:
        with tempfile.TemporaryDirectory(prefix="reindex-blob-") as directory:
            target = Path(directory) / "blob"
            with target.open("wb") as output:
                for index in range(session.blob_chunk_counts[sha256]):
                    key, _size = chunks[index]
                    with self.store.open(key) as source:
                        shutil.copyfileobj(source, output, 1024 * 1024)
            if target.stat().st_size != int(declared["byte_size"]):
                raise ValueError("assembled blob size mismatch")
            result = self.upload_blob(session.id, sha256, target)
        session.blob_chunks.pop(sha256, None)
        session.blob_chunk_counts.pop(sha256, None)
        return {**result, "status": result["status"], "received": len(chunks), "total": len(chunks)}
