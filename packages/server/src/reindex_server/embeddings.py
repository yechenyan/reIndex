from __future__ import annotations

import os
from collections.abc import Iterable


class EmbeddingProvider:
    name = "disabled"

    def embed_documents(self, values: Iterable[str]) -> list[list[float]]:
        raise RuntimeError("local embeddings are disabled; set REINDEX_EMBEDDINGS=qwen")

    def embed_query(self, value: str) -> list[float]:
        raise RuntimeError("local embeddings are disabled; set REINDEX_EMBEDDINGS=qwen")


class QwenEmbeddingProvider(EmbeddingProvider):
    name = "Qwen/Qwen3-Embedding-0.6B@1024"

    def __init__(self) -> None:
        self._model = None

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as error:
                raise RuntimeError("install reindex-server[embeddings] to enable Qwen embeddings") from error
            self._model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B", truncate_dim=1024)
        return self._model

    def embed_documents(self, values: Iterable[str]) -> list[list[float]]:
        return self.model.encode(list(values), normalize_embeddings=True).tolist()

    def embed_query(self, value: str) -> list[float]:
        return self.model.encode([value], prompt_name="query", normalize_embeddings=True)[0].tolist()


def provider_from_environment() -> EmbeddingProvider:
    return QwenEmbeddingProvider() if os.getenv("REINDEX_EMBEDDINGS") == "qwen" else EmbeddingProvider()
