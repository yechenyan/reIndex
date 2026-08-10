from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

from reindex_server.publication_support import PublicationSupportMixin
from reindex_cli import remote_ops


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


def test_push_embeds_before_creating_upload_session(monkeypatch) -> None:
    events: list[str] = []

    class Client:
        def json(self, path, payload):
            events.append(path)
            if path == "/v1/push":
                return {"upload_id": "upload-1", "missing_blobs": []}
            assert path == "/v1/push/commit"
            assert payload["embeddings"] == {"profile": "local", "vectors": {}}
            return {"version_id": "version-1", "uploaded_blobs": 0}

    context = SimpleNamespace(
        root=Path("/collection"),
        output_dir=Path("/collection/reIndex"),
        collection_id="collection-1",
        state={"name": "Collection"},
    )
    monkeypatch.setattr(remote_ops, "resolve_collection", lambda path: context)
    monkeypatch.setattr(remote_ops, "load_conflicts", lambda root: False)
    monkeypatch.setattr(remote_ops, "check_collection", lambda context: {"status": "valid"})
    monkeypatch.setattr(remote_ops, "build_transport_manifest", lambda context: ({}, {}))
    monkeypatch.setattr(remote_ops, "get_api_url", lambda url: "https://api.example")
    monkeypatch.setattr(remote_ops, "_optional_remote", lambda root: None)
    monkeypatch.setattr(remote_ops, "ApiClient", lambda url: Client())
    monkeypatch.setattr(
        remote_ops,
        "local_embeddings",
        lambda package, root: events.append("embed") or {"profile": "local", "vectors": {}},
    )
    monkeypatch.setattr(remote_ops, "cache_manifest", lambda *args: None)
    monkeypatch.setattr(remote_ops, "write_remote", lambda *args: None)

    assert remote_ops.push_collection(Path("/collection"))["version_id"] == "version-1"
    assert events == ["embed", "/v1/push", "/v1/push/commit"]
