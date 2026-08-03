from __future__ import annotations

import os
from pathlib import Path

from reindex_server.catalog import Catalog
from reindex_server.memory_search import MemorySearchBackend
from reindex_server.service import ReindexService
from reindex_server.storage import FileStore
from version_conflict_scenario import exercise_conflict_flow
from version_flow_support import (
    CountingEmbeddings,
    build_fixture,
    history,
    run_cli,
    serve,
)
from version_rollback_scenario import exercise_resolution_and_rollback


def test_test4_all_versioned_http_cli_flow(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setenv("REINDEX_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("REINDEX_CONFIG_HOME", str(tmp_path / "config"))
    external_url = os.getenv("REINDEX_VERSION_E2E_BASE_URL")
    embeddings = None
    server = thread = None
    if external_url:
        api_url = external_url
    else:
        embeddings = CountingEmbeddings()
        service = ReindexService(
            Catalog(),
            FileStore(tmp_path / "server-objects"),
            embeddings,
            MemorySearchBackend(),
        )
        server, thread, api_url = serve(service)
    try:
        client_a = build_fixture(tmp_path, capsys)
        original_raw = (client_a / "costs_2020.csv").read_bytes()

        first = run_cli(
            capsys,
            "push",
            str(client_a),
            "--api-url",
            api_url,
            "--message",
            "Initial test4-all import",
        )
        v1 = first["version_id"]
        package_v1 = first["package_hash"]
        assert first["status"] == "ready"
        assert first["uploaded_blobs"] > 0
        assert first["no_op"] is False
        embedded_v1 = embeddings.document_count if embeddings else None
        if embeddings:
            assert embedded_v1 > 0

        repeated = run_cli(capsys, "push", str(client_a), "--api-url", api_url)
        assert repeated["no_op"] is True
        assert repeated["version_id"] == v1
        assert repeated["uploaded_blobs"] == 0
        if embeddings:
            assert embeddings.document_count == embedded_v1
        assert len(history(capsys, api_url)["versions"]) == 1

        client_b, v2 = exercise_conflict_flow(
            capsys,
            tmp_path,
            api_url,
            client_a,
            v1,
            first,
            embeddings,
            embedded_v1,
        )
        exercise_resolution_and_rollback(
            capsys,
            tmp_path,
            api_url,
            client_a,
            client_b,
            original_raw,
            v1,
            v2,
            package_v1,
            embeddings,
        )
    finally:
        if server and thread:
            server.should_exit = True
            thread.join(timeout=10)
