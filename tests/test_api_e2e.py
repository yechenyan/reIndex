"""Black-box HTTP E2E test for an already running ReIndex API.

Set REINDEX_E2E_BASE_URL (for example http://127.0.0.1:8000) to enable it.
The test intentionally does not start or reset a database: the operator owns the
service lifecycle, while every run imports the deterministic testbase fixture.
"""

from __future__ import annotations

import io
import os
import time
import zipfile
from pathlib import Path

import httpx
import pytest

BASE_URL = os.getenv("REINDEX_E2E_BASE_URL")
IMPORT_TIMEOUT = float(os.getenv("REINDEX_E2E_IMPORT_TIMEOUT", "180"))
pytestmark = pytest.mark.skipif(
    not BASE_URL, reason="set REINDEX_E2E_BASE_URL to run HTTP E2E tests"
)

ROOT_ID = "056e95b3-aad8-4740-af7e-973356ec4e44"
DOCUMENT_ID = "be043b2f-0d57-40f7-aaa4-c7d6a99b55e6"
TABLE_ID = "333563cf-1334-45a5-9d19-55f53f79757f"


def test_testbase_fixture_over_real_http() -> None:
    _fixture_root, package, source, archive = _fixture()
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        assert client.get("/health").json()["status"] == "ok"
        _ensure_collection(client, package)

        upload = client.post(
            "/v1/raw/upload",
            data={"collection_id": ROOT_ID, "raw_path": source.name},
            files={"file": (source.name, source.read_bytes(), "application/pdf")},
        )
        assert upload.status_code == 200, upload.text
        assert upload.json()["sha256"]

        imported = client.post(
            "/v1/reindex/import",
            data={"collection_id": ROOT_ID},
            files={"archive": ("testbase-test1.zip", archive, "application/zip")},
        )
        assert imported.status_code == 202, imported.text
        status = _wait_until_ready(client)
        assert status["progress"]["nodes"] == 8

        direct = client.post(
            "/v1/nodes/browse",
            json={"collection_id": ROOT_ID, "parent_node_id": ROOT_ID},
        )
        assert direct.status_code == 200, direct.text
        assert [node["id"] for node in direct.json()["nodes"]] == [DOCUMENT_ID]
        subtree = client.post(
            "/v1/nodes/browse",
            json={
                "collection_id": ROOT_ID,
                "parent_node_id": DOCUMENT_ID,
                "recursive": True,
            },
        )
        assert [node["order"] for node in subtree.json()["nodes"]] == list(range(1, 7))

        detail = client.post(
            "/v1/nodes/get", json={"collection_id": ROOT_ID, "node_id": TABLE_ID}
        )
        assert detail.status_code == 200, detail.text
        assert {item["role"] for item in detail.json()["resources"]} == {
            "card",
            "source",
            "content",
            "asset",
        }

        search = client.post(
            "/v1/search",
            json={
                "collection_id": ROOT_ID,
                "query": "Bielefelder",
                "mode": "lexical",
            },
        )
        assert search.status_code == 200, search.text
        assert search.json()["results"]
        assert search.json()["results"][0]["evidence"]["unit_type"] == "card"
        grep = client.post(
            "/v1/grep",
            json={"collection_id": ROOT_ID, "pattern": "Bielefelder", "limit": 10},
        )
        assert grep.status_code == 200, grep.text
        assert grep.json()["executed_mode"] == "grep"
        assert grep.json()["results"]

        table = client.post(
            "/v1/tables/query",
            json={
                "collection_id": ROOT_ID,
                "node_id": TABLE_ID,
                "sql": "SELECT count(*) AS total FROM data",
            },
        )
        assert table.status_code == 200, table.text
        assert table.json()["rows"] == [{"total": 24}]

        raw = client.post(
            "/v1/raw/download", json={"collection_id": ROOT_ID, "raw_path": source.name}
        )
        assert raw.status_code == 200
        assert raw.content == source.read_bytes()
        _assert_downloads(client, package, source)


def _ensure_collection(client: httpx.Client, package: Path) -> None:
    status = client.post("/v1/collections/status", json={"collection_id": ROOT_ID})
    if status.status_code == 200:
        return
    assert status.status_code == 404, status.text
    created = client.post(
        "/v1/collections/create",
        files={
            "root_node": ("index.node.md", (package / "index.node.md").read_bytes())
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["collection_id"] == ROOT_ID


def _wait_until_ready(client: httpx.Client) -> dict:
    deadline = time.monotonic() + IMPORT_TIMEOUT
    latest: dict | None = None
    while time.monotonic() < deadline:
        response = client.post(
            "/v1/collections/status", json={"collection_id": ROOT_ID}
        )
        assert response.status_code == 200, response.text
        latest = response.json()
        if latest["status"] == "ready":
            return latest
        assert latest["status"] != "failed", latest
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting for import: {latest}")


def _assert_downloads(client: httpx.Client, package: Path, source: Path) -> None:
    document = package / "bielefelder-netz-gmbh-netzausbauplan-2022"
    expected = {
        "card": document
        / "00005--aggregierte-10-jahresplanung-untere-netzebenen.node.md",
        "source": source,
        "content": document
        / "00005--aggregierte-10-jahresplanung-untere-netzebenen.csv",
        "asset": document
        / "00005--aggregierte-10-jahresplanung-untere-netzebenen.assets001.png",
    }
    for target, file in expected.items():
        payload = {"collection_id": ROOT_ID, "node_id": TABLE_ID, "target": target}
        if target == "asset":
            payload["asset_ordinal"] = 1
        response = client.post("/v1/nodes/download", json=payload)
        assert response.status_code == 200, response.text
        assert response.content == file.read_bytes()


def _fixture() -> tuple[Path, Path, Path, bytes]:
    fixture = Path(__file__).resolve().parents[1] / "testbase" / "test1"
    package = fixture / "reIndex" / "test1"
    source = (
        fixture
        / "test1"
        / "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
    )
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        for file in package.rglob("*"):
            if file.is_file():
                bundle.write(
                    file, (Path(package.name) / file.relative_to(package)).as_posix()
                )
    return fixture, package, source, archive.getvalue()
