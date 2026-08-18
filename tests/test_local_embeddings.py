import hashlib
import json
import sys

import pytest

from reindex_cli.errors import ReIndexError
from reindex_cli.local_embeddings import PROFILE, _embedding_options, local_embeddings


def test_complete_embedding_cache_does_not_require_model_dependency(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    text = "title\ndescription\nbody"
    digest = hashlib.sha256(text.encode()).hexdigest()
    cache = tmp_path / ".rei" / "cache" / "embeddings" / f"{PROFILE}.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({digest: [0.1, 0.2]}), encoding="utf-8")
    monkeypatch.setattr(
        "reindex_cli.local_embeddings._search_texts", lambda package, root: [text]
    )
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)

    result = local_embeddings(tmp_path / "package", tmp_path)

    assert result == {"profile": PROFILE, "vectors": {digest: [0.1, 0.2]}}


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
