from __future__ import annotations

import json
import shutil
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from reindex_cli.cli import main
from reindex_server.app import create_app
from reindex_server.catalog import Catalog
from reindex_server.embeddings import EmbeddingProvider
from reindex_server.memory_search import MemorySearchBackend
from reindex_server.service import ReindexService
from reindex_server.storage import FileStore

ROOT = Path(__file__).resolve().parents[1]
TEST2 = ROOT / "testbase" / "test2-generage"


@pytest.fixture
def api_url(tmp_path: Path):
    service = ReindexService(
        Catalog(),
        FileStore(tmp_path / "server-objects"),
        EmbeddingProvider(),
        MemorySearchBackend(),
    )
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(service), host="127.0.0.1", port=port, log_level="error"
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)
    if not server.started:
        raise RuntimeError("test HTTP server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


def test_real_http_push_pull_and_full_flow(
    tmp_path: Path, api_url: str, capsys, monkeypatch
) -> None:
    monkeypatch.setenv("REINDEX_CACHE_HOME", str(tmp_path / "cache"))
    push_root = tmp_path / "test2-generage"
    shutil.copytree(
        TEST2,
        push_root,
        ignore=shutil.ignore_patterns("cache", "staging", "remote.json"),
    )
    assert main(["push", str(push_root), "--api-url", api_url]) == 0
    pushed = _output(capsys)
    assert pushed["status"] == "ready"
    assert pushed["sources"] == 2

    download = tmp_path / "test3-download"
    assert (
        main(
            [
                "pull",
                "test2-generage",
                "--output",
                str(download),
                "--api-url",
                api_url,
            ]
        )
        == 0
    )
    pulled = _output(capsys)
    node_dir = Path(pulled["node_dir"])
    assert pulled["nodes"] == 12
    assert all(
        path.name.endswith(".node.md") for path in node_dir.rglob("*") if path.is_file()
    )
    assert main(["search", "Technology costs", "--path", str(download)]) == 0
    assert _output(capsys)["results"]
    assert (
        main(
            [
                "get",
                "technology-costs-2020.node.md",
                "--target",
                "content",
                "--path",
                str(download),
            ]
        )
        == 0
    )
    assert _output(capsys)["source"] == "download"
    assert (
        main(
            [
                "get",
                "technology-costs-2020.node.md",
                "--target",
                "content",
                "--path",
                str(download),
            ]
        )
        == 0
    )
    assert _output(capsys)["source"] == "cache"

    full = tmp_path / "test4-all"
    full.mkdir()
    for name in (
        "reIndex.md",
        "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf",
        "00005--aggregierte-10-jahresplanung-untere-netzebenen.csv",
        "00006--massnahmenplan-aller-spannungsebenen.csv",
        "costs_2020.csv",
    ):
        shutil.copy2(TEST2 / name, full / name)
    assert (
        main(
            [
                "init",
                str(full),
                "--name",
                "test4-all",
                "--codex-home",
                str(tmp_path / "codex"),
            ]
        )
        == 0
    )
    _output(capsys)
    assert main(["scan", str(full)]) == 0
    assert _output(capsys)["nodes"] == 12
    assert main(["push", str(full), "--api-url", api_url]) == 0
    assert _output(capsys)["status"] == "ready"
    assert main(["search", "Technology costs", "--path", str(full)]) == 0
    assert _output(capsys)["results"]
    assert main(["get", "raw://costs_2020.csv", "--path", str(full)]) == 0
    assert _output(capsys)["source"] == "local"

    costs = full / "costs_2020.csv"
    original = costs.read_text(encoding="utf-8")
    changed = original.replace(",4.3,%/year", ",4.31,%/year", 1)
    assert changed != original
    costs.write_text(changed, encoding="utf-8")
    assert main(["scan", str(full)]) == 0
    _output(capsys)
    assert main(["push", str(full), "--api-url", api_url]) == 0
    assert _output(capsys)["status"] == "ready"
    response = httpx.post(
        f"{api_url}/v1/get",
        json={"collection": "test4-all", "raw_uri": "raw://costs_2020.csv"},
        timeout=30,
    )
    assert response.status_code == 200
    assert response.content == costs.read_bytes()


def _output(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def _free_port() -> int:
    with socket.socket() as stream:
        stream.bind(("127.0.0.1", 0))
        return int(stream.getsockname()[1])
