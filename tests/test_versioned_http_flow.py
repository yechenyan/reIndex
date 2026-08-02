from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from reindex_server.catalog import Catalog
from reindex_server.memory_search import MemorySearchBackend
from reindex_server.service import ReindexService
from reindex_server.storage import FileStore
from version_flow_support import (
    B_MARKER,
    RESOLVED_MARKER,
    TECHNOLOGY_CARD,
    V2_MARKER,
    CountingEmbeddings,
    assert_complete_downloads,
    assert_node_only,
    build_fixture,
    card,
    history,
    json_file,
    replace_marker,
    run_cli,
    run_cli_error,
    serve,
    worktree_files,
)


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

        client_b = tmp_path / "client-b"
        shutil.copytree(client_a, client_b)
        clean_authoring = tmp_path / "clean-authoring"
        shutil.copytree(client_a, clean_authoring)
        clean_checkout = tmp_path / "clean-checkout"
        pulled_v1 = run_cli(
            capsys,
            "pull",
            "test4-all",
            "--output",
            str(clean_checkout),
            "--api-url",
            api_url,
        )
        assert pulled_v1["version_id"] == v1
        assert pulled_v1["nodes"] == 7
        assert_node_only(clean_checkout)

        replace_marker(client_a, "Ammonia cracker", V2_MARKER)
        run_cli(capsys, "scan", str(client_a))
        second = run_cli(
            capsys,
            "push",
            str(client_a),
            "--api-url",
            api_url,
            "--message",
            "Publish version two marker",
        )
        v2 = second["version_id"]
        assert second["parent_version_id"] == v1
        assert v2 != v1
        assert 0 < second["uploaded_blobs"] < first["uploaded_blobs"]
        if embeddings:
            assert embedded_v1 < embeddings.document_count < embedded_v1 * 2

        fast_forward = run_cli(capsys, "pull", "--path", str(clean_checkout))
        assert fast_forward["version_id"] == v2
        assert V2_MARKER in card(clean_checkout, TECHNOLOGY_CARD).read_text()

        authoring_before = worktree_files(clean_authoring)
        authoring_pull = run_cli_error(capsys, "pull", "--path", str(clean_authoring))
        assert "not replaced" in authoring_pull["error"].lower()
        assert worktree_files(clean_authoring) == authoring_before

        replace_marker(client_b, "Ammonia cracker", B_MARKER)
        run_cli(capsys, "scan", str(client_b))
        stale = run_cli_error(capsys, "push", str(client_b), "--api-url", api_url)
        assert "409" in stale["error"]
        assert "advanced" in stale["error"].lower()

        before_pull = worktree_files(client_b)
        fetched = run_cli(capsys, "fetch", str(client_b), "--api-url", api_url)
        assert fetched["base_version_id"] == v1
        assert fetched["head_version_id"] == v2
        conflict = run_cli_error(capsys, "pull", "--path", str(client_b))
        assert "conflict" in conflict["error"].lower()
        assert worktree_files(client_b) == before_pull
        remote = json_file(client_b / ".rei" / "remote.json")
        assert remote["base_version_id"] == v1
        assert remote["head_version_id"] == v2
        conflicts = json_file(client_b / ".rei" / "conflicts.json")
        assert conflicts["spec"] == "reindex/conflicts@1.0"
        assert "costs_2020.csv" in json.dumps(conflicts)
        blocked = run_cli_error(capsys, "push", str(client_b), "--api-url", api_url)
        assert "conflict" in blocked["error"].lower()
        assert len(history(capsys, api_url)["versions"]) == 2

        versions = history(capsys, api_url)
        assert [item["version_id"] for item in versions["versions"]] == [v2, v1]
        shown = run_cli(
            capsys,
            "history",
            "test4-all",
            "--version",
            v1,
            "--api-url",
            api_url,
        )
        assert shown["version_id"] == v1
        compared = run_cli(
            capsys,
            "diff",
            "test4-all",
            "--from",
            v1,
            "--to",
            v2,
            "--api-url",
            api_url,
        )
        assert "costs_2020.csv" in json.dumps(compared)

        old_raw = tmp_path / "old-costs.csv"
        historical_get = run_cli(
            capsys,
            "get",
            "raw://costs_2020.csv",
            "--path",
            str(client_a),
            "--version",
            v1,
            "--output",
            str(old_raw),
        )
        assert historical_get["source"] == "download"
        assert old_raw.read_bytes() == original_raw
        historical_checkout = tmp_path / "historical-checkout"
        old_pull = run_cli(
            capsys,
            "pull",
            "test4-all",
            "--output",
            str(historical_checkout),
            "--version",
            v1,
            "--api-url",
            api_url,
        )
        assert old_pull["version_id"] == v1
        assert_node_only(historical_checkout)
        assert V2_MARKER not in card(historical_checkout, TECHNOLOGY_CARD).read_text()

        shutil.copy2(client_a / "costs_2020.csv", client_b / "costs_2020.csv")
        run_cli(capsys, "scan", str(client_b))
        resolved_card = card(client_b, TECHNOLOGY_CARD)
        resolved_card.write_text(
            resolved_card.read_text() + f"\n{RESOLVED_MARKER}.\n", encoding="utf-8"
        )
        continued = run_cli(capsys, "pull", "--path", str(client_b), "--continue")
        assert continued["base_version_id"] == v2
        assert not (client_b / ".rei" / "conflicts.json").exists()
        resolved = run_cli(
            capsys,
            "push",
            str(client_b),
            "--api-url",
            api_url,
            "--message",
            "Resolve local conflict",
        )
        v3 = resolved["version_id"]
        assert resolved["parent_version_id"] == v2

        current_checkout = tmp_path / "current-checkout"
        run_cli(
            capsys,
            "pull",
            "test4-all",
            "--output",
            str(current_checkout),
            "--api-url",
            api_url,
        )
        assert_complete_downloads(capsys, current_checkout, client_a)

        embedded_before_rollback = embeddings.document_count if embeddings else None
        rolled_back = run_cli(
            capsys,
            "rollback",
            "test4-all",
            v1,
            "--api-url",
            api_url,
            "--message",
            "Restore initial import",
        )
        v4 = rolled_back["version_id"]
        assert v4 not in {v1, v2, v3}
        assert rolled_back["parent_version_id"] == v3
        assert rolled_back["source_version_id"] == v1
        assert rolled_back["package_hash"] == package_v1
        assert rolled_back["uploaded_blobs"] == 0
        if embeddings:
            assert embeddings.document_count == embedded_before_rollback

        active = tmp_path / "after-rollback"
        run_cli(
            capsys,
            "pull",
            "test4-all",
            "--output",
            str(active),
            "--api-url",
            api_url,
        )
        marker_search = run_cli(capsys, "search", V2_MARKER, "--path", str(active))
        assert V2_MARKER not in json.dumps(marker_search)
        assert run_cli(capsys, "search", "Ammonia cracker", "--path", str(active))[
            "results"
        ]
        restored_raw = tmp_path / "restored-costs.csv"
        run_cli(
            capsys,
            "get",
            "raw://costs_2020.csv",
            "--path",
            str(active),
            "--output",
            str(restored_raw),
        )
        assert restored_raw.read_bytes() == original_raw

        retained_v2 = tmp_path / "retained-v2.csv"
        run_cli(
            capsys,
            "get",
            "raw://costs_2020.csv",
            "--path",
            str(active),
            "--version",
            v2,
            "--output",
            str(retained_v2),
        )
        assert V2_MARKER.encode() in retained_v2.read_bytes()
        assert len(history(capsys, api_url)["versions"]) == 4
    finally:
        if server and thread:
            server.should_exit = True
            thread.join(timeout=10)
