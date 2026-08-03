import asyncio
import io
import zipfile
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from reindex_server.app import app, create_app
from reindex_server.catalog import Catalog
from reindex_server.embeddings import EmbeddingProvider
from reindex_server.service import ReindexService
from reindex_server.storage import FileStore
from server_flow_support import (
    ROOT_ID,
    TABLE_ID,
    TABLE_PATH,
    FixtureSearchBackend,
    fixture,
    push,
)


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
    assert {
        "/v1/push",
        "/v1/pull",
        "/v1/search",
        "/v1/get",
        "/v1/collections",
        "/v1/nodes/browse",
    } <= paths
    assert {
        "/v1/raw/upload",
        "/v1/import",
        "/v1/status",
        "/v1/nodes/resolve",
        "/v1/resources/download",
    }.isdisjoint(paths)


def test_synchronous_push_pull_search_and_get(tmp_path: Path) -> None:
    package, source = fixture()
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
            result = await push(client, "test1", package, source, None, race=True)
            assert result["status"] == "ready"
            assert result["name"] == "test1"
            assert result["collection_id"] == ROOT_ID
            assert result["nodes"] == 8
            assert result["sources"] == 1

            collections = await client.get("/v1/collections")
            assert collections.status_code == 200
            assert collections.json()["collections"] == [
                {
                    "name": "test1",
                    "collection_id": ROOT_ID,
                    "status": "ready",
                    "package_hash": result["package_hash"],
                    "active_version_id": result["version_id"],
                    "progress": {
                        "stage": "ready",
                        "nodes": result["nodes"],
                        "resources": result["resources"],
                        "search_units": result["search_units"],
                    },
                }
            ]

            browsed = await client.post(
                "/v1/nodes/browse",
                json={"collection": "test1", "recursive": True},
            )
            assert browsed.status_code == 200, browsed.text
            nodes = browsed.json()["nodes"]
            assert len(nodes) == 8
            assert nodes[0]["id"] == ROOT_ID
            table_node = next(item for item in nodes if item["id"] == TABLE_ID)
            assert table_node["kind"] == "table"

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

            renamed = await push(
                client, "renamed-test1", package, source, result["version_id"]
            )
            assert renamed["collection_id"] == ROOT_ID
            assert (
                await client.post("/v1/pull", json={"collection": "test1"})
            ).status_code == 404
            assert (
                await client.post("/v1/pull", json={"collection": "renamed-test1"})
            ).status_code == 200

    asyncio.run(request_actions())
