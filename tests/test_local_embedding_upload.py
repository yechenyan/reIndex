from __future__ import annotations

import hashlib
from types import SimpleNamespace

from reindex_server.publication_support import PublicationSupportMixin


class Catalog:
    def __init__(self) -> None:
        self.values = {}

    def get_cached_embeddings(self, profile, hashes):
        return {key: self.values[key] for key in hashes if key in self.values}

    def put_cached_embeddings(self, profile, values):
        self.values.update(values)


class Publications(PublicationSupportMixin):
    def __init__(self) -> None:
        self.catalog = Catalog()
        self.embeddings = SimpleNamespace(name="disabled")


def test_local_vectors_publish_when_server_embeddings_are_disabled() -> None:
    unit = SimpleNamespace(contextual_text="title\ndescription\nbody", embedding=None)
    supplied = SimpleNamespace(profile="qwen3-embedding-0.6b@1024", vectors={})
    digest = hashlib.sha256(unit.contextual_text.encode()).hexdigest()
    supplied.vectors[digest] = [0.1, 0.2]
    profile, embedded, reused = Publications()._embed([unit], supplied)
    assert (profile, embedded, reused) == ("qwen3-embedding-0.6b@1024", 1, 0)
    assert unit.embedding == [0.1, 0.2]
