"""Black-box synchronous push/pull/search/get test for a running ReIndex API."""

from __future__ import annotations

import io
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
    package, source, package_zip, sources_zip = _fixture()
    with httpx.Client(base_url=BASE_URL, timeout=1800.0) as client:
        assert client.get("/health").json()["status"] == "ok"
        pushed = client.post(
            "/v1/push",
            data={"name": "http-e2e-test1"},
            files={
                "package": ("package.zip", package_zip, "application/zip"),
                "sources": ("sources.zip", sources_zip, "application/zip"),
            },
        )
        assert pushed.status_code == 200, pushed.text
        assert pushed.json()["nodes"] == 8

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


def _fixture() -> tuple[Path, Path, bytes, bytes]:
    fixture = Path(__file__).resolve().parents[1] / "testbase" / "test1"
    package = fixture / "reIndex" / "test1"
    source = (
        fixture
        / "test1"
        / "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
    )
    package_zip = io.BytesIO()
    with zipfile.ZipFile(package_zip, "w") as bundle:
        for file in package.rglob("*"):
            if file.is_file():
                bundle.write(
                    file, (Path(package.name) / file.relative_to(package)).as_posix()
                )
    sources_zip = io.BytesIO()
    with zipfile.ZipFile(sources_zip, "w") as bundle:
        bundle.write(source, source.name)
    return package, source, package_zip.getvalue(), sources_zip.getvalue()
