from reindex_server.embeddings import (
    EmbeddingProvider,
    QwenEmbeddingProvider,
    provider_from_environment,
)
from reindex_server.reranking import Reranker
from reindex_server.reranking import (
    provider_from_environment as reranker_from_environment,
)


def test_qwen_embeddings_are_enabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("REINDEX_EMBEDDINGS", raising=False)
    assert isinstance(provider_from_environment(), QwenEmbeddingProvider)


def test_embeddings_can_be_explicitly_disabled(monkeypatch) -> None:
    monkeypatch.setenv("REINDEX_EMBEDDINGS", "disabled")
    provider = provider_from_environment()
    assert type(provider) is EmbeddingProvider


def test_invalid_embedding_provider_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("REINDEX_EMBEDDINGS", "unknown")
    try:
        provider_from_environment()
    except ValueError as error:
        assert str(error) == "REINDEX_EMBEDDINGS must be qwen or disabled"
    else:
        raise AssertionError("invalid embedding provider was accepted")


def test_reranking_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("REINDEX_RERANKER", raising=False)
    assert type(reranker_from_environment()) is Reranker
