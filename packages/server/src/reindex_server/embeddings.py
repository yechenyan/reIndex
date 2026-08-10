from __future__ import annotations

import os
from collections.abc import Iterable
from threading import Lock


class EmbeddingProvider:
    name = "disabled"

    def embed_documents(self, values: Iterable[str]) -> list[list[float]]:
        raise RuntimeError("local embeddings are disabled; set REINDEX_EMBEDDINGS=qwen")

    def embed_query(self, value: str) -> list[float]:
        raise RuntimeError("local embeddings are disabled; set REINDEX_EMBEDDINGS=qwen")

    def warmup(self) -> None:
        return None


class QwenEmbeddingProvider(EmbeddingProvider):
    name = "qwen3-embedding-0.6b@1024"

    def __init__(self) -> None:
        self._model = None
        self._lock = Lock()

    @property
    def model(self):
        with self._lock:
            if self._model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError as error:
                    raise RuntimeError(
                        "install reindex-server[embeddings] to enable Qwen embeddings"
                    ) from error
                self._model = SentenceTransformer(
                    "Qwen/Qwen3-Embedding-0.6B", truncate_dim=1024
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
