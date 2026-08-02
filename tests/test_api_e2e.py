"""Black-box versioned push/pull/search/get test for a running ReIndex API."""

from __future__ import annotations

import hashlib
import io
import mimetypes
import os
import zipfile
from pathlib import Path

import httpx
import pytest

BASE_URL = os.getenv("REINDEX_E2E_BASE_URL")
pytestmark = pytest.mark.skipif(
    not BASE_URL, reason="set REINDEX_E2E_BASE_URL to run HTTP E2E tests"
)

TABLE_ID = "333563cf-1334-45a5-9d19-55f53f79757f"
TABLE_PATH = (
    "bielefelder-netz-gmbh-netzausbauplan-2022/"
    "00005--aggregierte-10-jahresplanung-untere-netzebenen.node.md"
)


def test_fixture_over_real_http() -> None:
    package, source = _fixture()
    with httpx.Client(base_url=BASE_URL, timeout=1800.0) as client:
        assert client.get("/health").json()["status"] == "ok"
        pushed = _push(client, package, source)
        assert pushed["nodes"] == 8

        search = client.post(
            "/v1/search",
            json={
                "collection": "http-e2e-test1",
                "query": "Bielefelder",
                "mode": "lexical",
            },
        )
        assert search.status_code == 200, search.text
        assert search.json()["results"]

        content = client.post(
            "/v1/get",
            json={
                "collection": "http-e2e-test1",
                "node_path": TABLE_PATH,
                "target": "content",
            },
        )
        expected = package / TABLE_PATH.replace(".node.md", ".csv")
        assert content.content == expected.read_bytes()
        raw = client.post(
            "/v1/get",
            json={
                "collection": "http-e2e-test1",
                "raw_uri": f"raw://{source.name}",
            },
        )
        assert raw.content == source.read_bytes()

        table = client.post(
            "/v1/tables/query",
            json={
                "collection": "http-e2e-test1",
                "node_id": TABLE_ID,
                "sql": "SELECT count(*) AS total FROM data",
            },
        )
        assert table.json()["rows"] == [{"total": 24}]
        pulled = client.post("/v1/pull", json={"collection": "http-e2e-test1"})
        with zipfile.ZipFile(io.BytesIO(pulled.content)) as bundle:
            assert len(bundle.namelist()) == 8
            assert all(name.endswith(".node.md") for name in bundle.namelist())


def _fixture() -> tuple[Path, Path]:
    fixture = Path(__file__).resolve().parents[1] / "testbase" / "test1"
    package = fixture / "reIndex" / "test1"
    source = (
        fixture
        / "test1"
        / "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
    )
    return package, source


def _push(client: httpx.Client, package: Path, source: Path) -> dict:
    files = []
    blobs = {}
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        _add_file(files, blobs, "package", path.relative_to(package).as_posix(), path)
    _add_file(files, blobs, "raw", source.name, source)
    started = client.post(
        "/v1/push",
        json={
            "name": "http-e2e-test1",
            "collection_id": "056e95b3-aad8-4740-af7e-973356ec4e44",
            "base_version_id": None,
            "message": "External HTTP fixture",
            "manifest": {
                "spec": "reindex/transport@1.0",
                "package_root": package.name,
                "files": files,
            },
        },
    )
    assert started.status_code == 200, started.text
    plan = started.json()
    for item in plan["missing_blobs"]:
        path = blobs[item["sha256"]]
        uploaded = client.post(
            "/v1/push/blob",
            data={"upload_id": plan["upload_id"], "sha256": item["sha256"]},
            files={"blob": (path.name, path.read_bytes())},
        )
        assert uploaded.status_code == 200, uploaded.text
    committed = client.post("/v1/push/commit", json={"upload_id": plan["upload_id"]})
    assert committed.status_code == 200, committed.text
    return committed.json()


def _add_file(files, blobs, namespace, logical_path, path) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    blobs[digest] = path
    files.append(
        {
            "namespace": namespace,
            "logical_path": logical_path,
            "sha256": digest,
            "byte_size": path.stat().st_size,
            "media_type": mimetypes.guess_type(path.name)[0]
            or "application/octet-stream",
        }
    )
