import asyncio
import io
import zipfile
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from reindex_server.app import app, create_app
from reindex_server.catalog import Catalog
from reindex_server.domain import SearchHit
from reindex_server.embeddings import EmbeddingProvider
from reindex_server.service import ReindexService
from reindex_server.storage import FileStore

ROOT_ID = "056e95b3-aad8-4740-af7e-973356ec4e44"
DOCUMENT_ID = "be043b2f-0d57-40f7-aaa4-c7d6a99b55e6"
TABLE_ID = "333563cf-1334-45a5-9d19-55f53f79757f"


class FixtureSearchBackend:
    def search(self, collection, options, query_embedding):
        unit = next(
            unit
            for unit in collection.units
            if options.query.casefold() in unit.contextual_text.casefold()
        )
        return [SearchHit(unit, 1.0, ("lexical",), {"lexical": 1}, bm25_score=1.0)]

    def grep(self, collection, pattern, limit, regex, case_sensitive):
        return []


def test_health() -> None:
    async def request_health():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health")

    response = asyncio.run(request_health())
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_testbase_collection_import_and_actions(tmp_path: Path) -> None:
    _, package, source, archive = _fixture()
    service = ReindexService(
        Catalog(),
        FileStore(tmp_path / "objects"),
        EmbeddingProvider(),
        FixtureSearchBackend(),
    )
    test_app = create_app(service)

    async def request_actions() -> None:
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/collections/create",
                files={
                    "root_node": (
                        "index.node.md",
                        (package / "index.node.md").read_bytes(),
                    )
                },
            )
            assert response.status_code == 200
            assert response.json()["collection_id"] == ROOT_ID
            response = await client.post(
                "/v1/raw/upload",
                data={"collection_id": ROOT_ID, "raw_path": source.name},
                files={"file": (source.name, source.read_bytes(), "application/pdf")},
            )
            assert response.status_code == 200
            conflict = await client.post(
                "/v1/raw/upload",
                data={"collection_id": ROOT_ID, "raw_path": source.name},
                files={"file": (source.name, b"different", "application/pdf")},
            )
            assert conflict.status_code == 409
            assert conflict.json()["error"]["code"] == "conflict"
            response = await client.post(
                "/v1/reindex/import",
                data={"collection_id": ROOT_ID},
                files={"archive": ("fixture.zip", archive, "application/zip")},
            )
            assert response.status_code == 202
            status = await client.post(
                "/v1/collections/status", json={"collection_id": ROOT_ID}
            )
            assert status.json()["status"] == "ready"
            assert status.json()["package_hash"]
            assert status.json()["progress"]["nodes"] == 8

            direct = await client.post(
                "/v1/nodes/browse",
                json={"collection_id": ROOT_ID, "parent_node_id": ROOT_ID},
            )
            assert [node["id"] for node in direct.json()["nodes"]] == [DOCUMENT_ID]
            subtree = await client.post(
                "/v1/nodes/browse",
                json={
                    "collection_id": ROOT_ID,
                    "parent_node_id": DOCUMENT_ID,
                    "recursive": True,
                },
            )
            assert [node["order"] for node in subtree.json()["nodes"]] == list(
                range(1, 7)
            )

            detail = await client.post(
                "/v1/nodes/get", json={"collection_id": ROOT_ID, "node_id": TABLE_ID}
            )
            assert [item["role"] for item in detail.json()["resources"]] == [
                "card",
                "source",
                "content",
                "asset",
            ]
            search = await client.post(
                "/v1/search",
                json={
                    "collection_id": ROOT_ID,
                    "query": "Bielefelder",
                    "mode": "lexical",
                },
            )
            assert search.status_code == 200
            assert search.json()["results"][0]["evidence"]["unit_type"] == "card"
            table = await client.post(
                "/v1/tables/query",
                json={
                    "collection_id": ROOT_ID,
                    "node_id": TABLE_ID,
                    "sql": "SELECT count(*) AS total FROM data",
                },
            )
            assert table.json()["rows"] == [{"total": 24}]
            raw = await client.post(
                "/v1/raw/download",
                json={"collection_id": ROOT_ID, "raw_path": source.name},
            )
            assert raw.content == source.read_bytes()
            await _assert_downloads(client, package, source)

            failed = await client.post(
                "/v1/reindex/import",
                data={"collection_id": ROOT_ID},
                files={
                    "archive": (
                        "invalid.zip",
                        _corrupt_content(archive),
                        "application/zip",
                    )
                },
            )
            assert failed.status_code == 202
            status = await client.post(
                "/v1/collections/status", json={"collection_id": ROOT_ID}
            )
            assert status.json()["status"] == "failed"
            preserved = await client.post(
                "/v1/nodes/get",
                json={"collection_id": ROOT_ID, "node_id": TABLE_ID},
            )
            assert preserved.status_code == 200
            preserved_search = await client.post(
                "/v1/search",
                json={
                    "collection_id": ROOT_ID,
                    "query": "Bielefelder",
                    "mode": "lexical",
                },
            )
            assert preserved_search.status_code == 200

    asyncio.run(request_actions())


async def _assert_downloads(client, package: Path, source: Path) -> None:
    document = package / "bielefelder-netz-gmbh-netzausbauplan-2022"
    targets = {
        "card": document
        / "00005--aggregierte-10-jahresplanung-untere-netzebenen.node.md",
        "source": source,
        "content": document
        / "00005--aggregierte-10-jahresplanung-untere-netzebenen.csv",
        "asset": document
        / "00005--aggregierte-10-jahresplanung-untere-netzebenen.assets001.png",
    }
    for target, expected in targets.items():
        payload = {"collection_id": ROOT_ID, "node_id": TABLE_ID, "target": target}
        if target == "asset":
            payload["asset_ordinal"] = 1
        response = await client.post("/v1/nodes/download", json=payload)
        assert response.status_code == 200
        assert response.content == expected.read_bytes()


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


def _corrupt_content(archive: bytes) -> bytes:
    incoming = zipfile.ZipFile(io.BytesIO(archive))
    output = io.BytesIO()
    target = "00005--aggregierte-10-jahresplanung-untere-netzebenen.csv"
    with incoming, zipfile.ZipFile(output, "w") as result:
        for item in incoming.infolist():
            content = incoming.read(item)
            result.writestr(
                item,
                content + b"\ncorrupt" if item.filename.endswith(target) else content,
            )
    return output.getvalue()
