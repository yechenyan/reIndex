from __future__ import annotations

import json
import shutil
import socket
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from reindex_cli.cli import main
from reindex_server.app import create_app
from reindex_server.embeddings import EmbeddingProvider
from reindex_server.service import ReindexService

ROOT = Path(__file__).resolve().parents[1]
TEST4 = ROOT / "testbase" / "test4-all"
INPUTS = (
    "reIndex.md",
    "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf",
    "00005--aggregierte-10-jahresplanung-untere-netzebenen.csv",
    "00006--massnahmenplan-aller-spannungsebenen.csv",
    "costs_2020.csv",
)
TECHNOLOGY_CARD = "technology-costs-2020.node.md"
TABLE_CARD = (
    "netzausbauplan-nach-14d-enwg/"
    "00008--aggregierte-10-jahresplanung-der-unteren-netzebenen.node.md"
)
EXPECTED_NODES = 12
V2_MARKER = "V2UNIQUESEARCHTOKEN"
B_MARKER = "Version B Conflict"
RESOLVED_MARKER = "Resolved local card note"


class CountingEmbeddings(EmbeddingProvider):
    name = "test/counting-embeddings@1"

    def __init__(self) -> None:
        self.document_count = 0

    def embed_documents(self, values):
        texts = list(values)
        self.document_count += len(texts)
        return [[float(len(value) % 101)] for value in texts]

    def embed_query(self, value: str) -> list[float]:
        return [float(len(value) % 101)]


def build_fixture(tmp_path: Path, capsys) -> Path:
    root = tmp_path / "client-a"
    root.mkdir()
    for name in INPUTS:
        shutil.copy2(TEST4 / name, root / name)
    run_cli(
        capsys,
        "init",
        str(root),
        "--name",
        "test4-all",
        "--codex-home",
        str(tmp_path / "codex"),
    )
    scanned = run_cli(capsys, "scan", str(root))
    assert scanned["nodes"] == EXPECTED_NODES
    return root


def assert_complete_downloads(capsys, checkout: Path, authoring: Path) -> None:
    outputs = {
        "card": (TECHNOLOGY_CARD, "card", None),
        "content": (TECHNOLOGY_CARD, "content", None),
        "source": (TECHNOLOGY_CARD, "source", None),
        "asset": (TABLE_CARD, "asset", "1"),
        "raw": ("raw://costs_2020.csv", None, None),
    }
    downloaded = {}
    for name, (reference, target, ordinal) in outputs.items():
        path = checkout.parent / f"download-{name}"
        args = ["get", reference, "--path", str(checkout), "--output", str(path)]
        if target:
            args.extend(("--target", target))
        if ordinal:
            args.extend(("--asset-ordinal", ordinal))
        run_cli(capsys, *args)
        downloaded[name] = path
    expected = (authoring / "costs_2020.csv").read_bytes()
    assert RESOLVED_MARKER in downloaded["card"].read_text()
    assert downloaded["content"].read_bytes() == expected
    assert downloaded["source"].read_bytes() == expected
    assert downloaded["raw"].read_bytes() == expected
    assert downloaded["asset"].read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def replace_marker(root: Path, old: str, new: str) -> None:
    path = root / "costs_2020.csv"
    content = path.read_text(encoding="utf-8")
    changed = content.replace(old, new, 1)
    assert changed != content
    path.write_text(changed, encoding="utf-8", newline="")


def history(capsys, api_url: str) -> dict:
    return run_cli(capsys, "history", "test4-all", "--api-url", api_url)


def run_cli(capsys, *args: str) -> dict:
    capsys.readouterr()
    assert main(list(args)) == 0
    captured = capsys.readouterr()
    return json.loads(captured.out)


def run_cli_error(capsys, *args: str) -> dict:
    capsys.readouterr()
    assert main(list(args)) == 1
    captured = capsys.readouterr()
    assert not captured.out
    return json.loads(captured.err)


def card(root: Path, name: str) -> Path:
    matches = list((root / "reIndex").rglob(name))
    assert len(matches) == 1
    return matches[0]


def assert_node_only(root: Path) -> None:
    files = [path for path in (root / "reIndex").rglob("*") if path.is_file()]
    assert len(files) == EXPECTED_NODES
    assert all(path.name.endswith(".node.md") for path in files)


def worktree_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ".rei" not in path.relative_to(root).parts
    }


def json_file(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def serve(
    service: ReindexService,
) -> tuple[uvicorn.Server, threading.Thread, str]:
    with socket.socket() as stream:
        stream.bind(("127.0.0.1", 0))
        port = int(stream.getsockname()[1])
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
    response = httpx.get(f"http://127.0.0.1:{port}/health", timeout=10)
    assert response.status_code == 200
    return server, thread, f"http://127.0.0.1:{port}"
