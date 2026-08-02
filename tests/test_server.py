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
TABLE_ID = "333563cf-1334-45a5-9d19-55f53f79757f"
TABLE_PATH = (
    "bielefelder-netz-gmbh-netzausbauplan-2022/"
    "00005--aggregierte-10-jahresplanung-untere-netzebenen.node.md"
)


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
    assert response.json() == {"status": "ok", "version": "0.2.0"}


def test_public_api_uses_the_canonical_synchronous_workflow() -> None:
    paths = {route.path for route in app.routes}
    assert {"/v1/push", "/v1/pull", "/v1/search", "/v1/get"} <= paths
    assert {
        "/v1/collections",
        "/v1/raw/upload",
        "/v1/import",
        "/v1/status",
        "/v1/nodes/resolve",
        "/v1/resources/download",
    }.isdisjoint(paths)


def test_synchronous_push_pull_search_and_get(tmp_path: Path) -> None:
    package, source, package_zip, sources_zip = _fixture()
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
            pushed = await client.post(
                "/v1/push",
                data={"name": "test1"},
                files={
                    "package": ("package.zip", package_zip, "application/zip"),
                    "sources": ("sources.zip", sources_zip, "application/zip"),
                },
            )
            assert pushed.status_code == 200, pushed.text
            result = pushed.json()
            assert result["status"] == "ready"
            assert result["name"] == "test1"
            assert result["collection_id"] == ROOT_ID
            assert result["nodes"] == 8
            assert result["sources"] == 1

            searched = await client.post(
                "/v1/search",
                json={"collection": "test1", "query": "Bielefelder", "mode": "lexical"},
            )
            assert searched.status_code == 200, searched.text
            hit = searched.json()["results"][0]
            assert hit["evidence"]["unit_type"] == "card"
            assert hit["get"]["target"] == "card"

            content = await client.post(
                "/v1/get",
                json={
                    "collection": "test1",
                    "node_path": TABLE_PATH,
                    "target": "content",
                },
            )
            expected = package / TABLE_PATH.replace(".node.md", ".csv")
            assert content.content == expected.read_bytes()
            assert content.headers["x-reindex-sha256"]
            assert int(content.headers["content-length"]) == len(content.content)

            raw = await client.post(
                "/v1/get",
                json={"collection": "test1", "raw_uri": f"raw://{source.name}"},
            )
            assert raw.content == source.read_bytes()

            table = await client.post(
                "/v1/tables/query",
                json={
                    "collection": "test1",
                    "node_id": TABLE_ID,
                    "sql": "SELECT count(*) AS total FROM data",
                },
            )
            assert table.json()["rows"] == [{"total": 24}]

            pulled = await client.post("/v1/pull", json={"collection": "test1"})
            assert pulled.status_code == 200
            with zipfile.ZipFile(io.BytesIO(pulled.content)) as bundle:
                assert len(bundle.namelist()) == 8
                assert all(name.endswith(".node.md") for name in bundle.namelist())
                assert (
                    bundle.read("index.node.md")
                    == (package / "index.node.md").read_bytes()
                )

            renamed = await client.post(
                "/v1/push",
                data={"name": "renamed-test1"},
                files={
                    "package": ("package.zip", package_zip, "application/zip"),
                    "sources": ("sources.zip", sources_zip, "application/zip"),
                },
            )
            assert renamed.status_code == 200, renamed.text
            assert renamed.json()["collection_id"] == ROOT_ID
            assert (
                await client.post("/v1/pull", json={"collection": "test1"})
            ).status_code == 404
            assert (
                await client.post("/v1/pull", json={"collection": "renamed-test1"})
            ).status_code == 200

    asyncio.run(request_actions())


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
