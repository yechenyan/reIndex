from __future__ import annotations

import os
from dataclasses import replace
from threading import RLock
from time import perf_counter

from reindex_server.domain import SearchHit


class Reranker:
    name = "disabled"
    candidate_limit = 0
    fusion_weight = 0.0

    def rerank(
        self, query: str, hits: list[SearchHit]
    ) -> tuple[list[SearchHit], float]:
        return hits, 0.0

    def warmup(self) -> None:
        return None


class MiniLMReranker(Reranker):
    """Small multilingual cross-encoder for second-stage retrieval ranking."""

    name = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

    def __init__(
        self,
        *,
        candidate_limit: int = 20,
        batch_size: int = 8,
        max_length: int = 512,
        fusion_weight: float = 0.75,
    ) -> None:
        self.candidate_limit = candidate_limit
        self.batch_size = batch_size
        self.max_length = max_length
        self.fusion_weight = fusion_weight
        self._model = None
        self._lock = RLock()

    @property
    def model(self):
        with self._lock:
            if self._model is None:
                try:
                    import torch
                    from sentence_transformers import CrossEncoder
                except ImportError as error:
                    raise RuntimeError(
                        "install reindex-server[embeddings] to enable reranking"
                    ) from error
                device = (
                    "cuda"
                    if torch.cuda.is_available()
                    else "mps"
                    if torch.backends.mps.is_available()
                    else "cpu"
                )
                self._model = CrossEncoder(
                    self.name, device=device, max_length=self.max_length
                )
        return self._model

    def rerank(
        self, query: str, hits: list[SearchHit]
    ) -> tuple[list[SearchHit], float]:
        candidates = hits[: self.candidate_limit]
        if not candidates:
            return hits, 0.0
        started = perf_counter()
        with self._lock:
            scores = self.model.predict(
                [(query, hit.unit.original_text) for hit in candidates],
                batch_size=self.batch_size,
                show_progress_bar=False,
            )
        reranked = [
            replace(hit, rerank_score=float(score))
            for score, hit in sorted(
                zip(scores, candidates, strict=True),
                key=lambda value: float(value[0]),
                reverse=True,
            )
        ]
        return reranked + hits[self.candidate_limit :], (
            perf_counter() - started
        ) * 1000

    def warmup(self) -> None:
        self.rerank("Initialize document retrieval.", [])
        self.model.predict(
            [("Initialize document retrieval.", "Warmup document.")],
            batch_size=1,
            show_progress_bar=False,
        )


def provider_from_environment() -> Reranker:
    value = os.getenv("REINDEX_RERANKER", "minilm")
    if value == "disabled":
        return Reranker()
    if value != "minilm":
        raise ValueError("REINDEX_RERANKER must be minilm or disabled")
    candidate_limit = int(os.getenv("REINDEX_RERANK_LIMIT", "20"))
    batch_size = int(os.getenv("REINDEX_RERANK_BATCH_SIZE", "8"))
    max_length = int(os.getenv("REINDEX_RERANK_MAX_LENGTH", "512"))
    fusion_weight = float(os.getenv("REINDEX_RERANK_WEIGHT", "0.75"))
    if candidate_limit < 1 or candidate_limit > 100:
        raise ValueError("REINDEX_RERANK_LIMIT must be between 1 and 100")
    if batch_size < 1 or batch_size > 128:
        raise ValueError("REINDEX_RERANK_BATCH_SIZE must be between 1 and 128")
    if max_length < 64 or max_length > 512:
        raise ValueError("REINDEX_RERANK_MAX_LENGTH must be between 64 and 512")
    if fusion_weight < 0 or fusion_weight > 10:
        raise ValueError("REINDEX_RERANK_WEIGHT must be between 0 and 10")
    return MiniLMReranker(
        candidate_limit=candidate_limit,
        batch_size=batch_size,
        max_length=max_length,
        fusion_weight=fusion_weight,
    )
