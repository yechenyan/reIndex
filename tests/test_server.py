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


def test_health() -> None:
    async def request_health():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health")

    response = asyncio.run(request_health())
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_collection_import_and_actions(tmp_path: Path) -> None:
    fixture = Path(__file__).resolve().parents[1] / "testbase" / "test1"
    package = fixture / "reIndex"
    source = fixture / "raw" / "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
    root = package / "index.node.md"
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        for file in package.rglob("*"):
            if file.is_file():
                bundle.write(file, file.relative_to(package).as_posix())
    service = ReindexService(Catalog(), FileStore(tmp_path / "objects"), EmbeddingProvider())
    test_app = create_app(service)

    async def request_actions() -> None:
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/collections/create", files={"root_node": ("index.node.md", root.read_bytes())})
            assert response.status_code == 200
            collection_id = response.json()["collection_id"]
            assert collection_id == "056e95b3-aad8-4740-af7e-973356ec4e44"

            response = await client.post(
                "/v1/raw/upload",
                data={"collection_id": collection_id, "raw_path": source.name},
                files={"file": (source.name, source.read_bytes(), "application/pdf")},
            )
            assert response.status_code == 200

            response = await client.post(
                "/v1/reindex/import",
                data={"collection_id": collection_id},
                files={"archive": ("fixture.zip", archive.getvalue(), "application/zip")},
            )
            assert response.status_code == 202
            response = await client.post("/v1/collections/status", json={"collection_id": collection_id})
            assert response.json()["status"] == "ready"

            response = await client.post("/v1/search", json={"collection_id": collection_id, "query": "Bielefelder", "mode": "lexical"})
            assert response.status_code == 200
            assert response.json()["results"]

            response = await client.post(
                "/v1/tables/query",
                json={"collection_id": collection_id, "node_id": "333563cf-1334-45a5-9d19-55f53f79757f", "sql": "SELECT count(*) AS total FROM data"},
            )
            assert response.status_code == 200
            assert response.json()["rows"] == [{"total": 24}]

            response = await client.post("/v1/raw/download", json={"collection_id": collection_id, "raw_path": source.name})
            assert response.status_code == 200
            assert response.content == source.read_bytes()

    asyncio.run(request_actions())
