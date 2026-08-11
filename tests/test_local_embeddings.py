import pytest

from reindex_cli.errors import ReIndexError
from reindex_cli.local_embeddings import _embedding_options


def test_embedding_options_default_to_small_mps_batches_on_macos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REINDEX_LOCAL_EMBEDDING_DEVICE", raising=False)
    monkeypatch.delenv("REINDEX_LOCAL_EMBEDDING_BATCH_SIZE", raising=False)
    monkeypatch.setattr("reindex_cli.local_embeddings.sys.platform", "darwin")

    assert _embedding_options() == ("mps", 2)


def test_embedding_options_validate_device_and_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REINDEX_LOCAL_EMBEDDING_DEVICE", "invalid")
    with pytest.raises(ReIndexError, match="DEVICE"):
        _embedding_options()
    monkeypatch.setenv("REINDEX_LOCAL_EMBEDDING_DEVICE", "cpu")
    monkeypatch.setenv("REINDEX_LOCAL_EMBEDDING_BATCH_SIZE", "0")
    with pytest.raises(ReIndexError, match="positive"):
        _embedding_options()
