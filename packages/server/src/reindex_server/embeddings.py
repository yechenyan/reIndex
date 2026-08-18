from __future__ import annotations

import os
import logging
import traceback
from collections.abc import Iterable
from pathlib import Path
from threading import Lock

logger = logging.getLogger("reindex.embeddings")


class EmbeddingProvider:
    name = "disabled"

    def embed_documents(self, values: Iterable[str]) -> list[list[float]]:
        raise RuntimeError("local embeddings are disabled; set REINDEX_EMBEDDINGS=qwen")

    def embed_query(self, value: str) -> list[float]:
        raise RuntimeError("local embeddings are disabled; set REINDEX_EMBEDDINGS=qwen")

    def warmup(self) -> None:
        return None

    def set_import_active(self, active: bool) -> None:
        return None


class QwenEmbeddingProvider(EmbeddingProvider):
    name = "qwen3-embedding-0.6b@1024"

    def __init__(self) -> None:
        self._model = None
        self._lock = Lock()
        self._import_active = False

    def set_import_active(self, active: bool) -> None:
        with self._lock:
            self._import_active = active
        logger.warning("qwen import guard active=%s", active)

    @property
    def model(self):
        with self._lock:
            if self._import_active:
                logger.error(
                    "blocked Qwen model load during import\n%s",
                    "".join(traceback.format_stack(limit=12)),
                )
                raise RuntimeError(
                    "server embedding model is suspended during local embedding import"
                )
            if self._model is None:
                logger.warning(
                    "loading Qwen model pid=%s\n%s",
                    os.getpid(),
                    "".join(traceback.format_stack(limit=12)),
                )
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError as error:
                    raise RuntimeError(
                        "install reindex-server[embeddings] to enable Qwen embeddings"
                    ) from error
                self._model = SentenceTransformer(
                    "Qwen/Qwen3-Embedding-0.6B",
                    cache_folder=str(_model_cache_dir()),
                    truncate_dim=1024,
                )
        return self._model

    def embed_documents(self, values: Iterable[str]) -> list[list[float]]:
        model = self.model
        with self._lock:
            return model.encode(list(values), normalize_embeddings=True).tolist()

    def embed_query(self, value: str) -> list[float]:
        model = self.model
        with self._lock:
            return model.encode(
                [value], prompt_name="query", normalize_embeddings=True
            )[0].tolist()

    def warmup(self) -> None:
        self.embed_query("Initialize multilingual document retrieval.")


def provider_from_environment() -> EmbeddingProvider:
    value = os.getenv("REINDEX_EMBEDDINGS", "qwen")
    if value == "qwen":
        return QwenEmbeddingProvider()
    if value == "disabled":
        return EmbeddingProvider()
    raise ValueError("REINDEX_EMBEDDINGS must be qwen or disabled")


def _model_cache_dir() -> Path:
    path = Path(os.getenv("REINDEX_DATA_DIR", ".reindex-data")) / "huggingface"
    path.mkdir(parents=True, exist_ok=True)
    return path
