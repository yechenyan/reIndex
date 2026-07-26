from __future__ import annotations

import asyncio
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from reindex_server.app import create_app
from reindex_server.catalog import Catalog
from reindex_server.domain import Collection, Node, SearchHit, SearchOptions, SearchUnit
from reindex_server.embeddings import EmbeddingProvider
from reindex_server.package_import import _markdown_chunks
from reindex_server.service import ReindexService
from reindex_server.storage import FileStore


class FakeEmbeddings(EmbeddingProvider):
    name = "test@1024"

    def embed_query(self, value: str) -> list[float]:
        return [0.0, 1.0]


class FakeSearchBackend:
    def __init__(self, units: list[SearchUnit]) -> None:
        self.units = units
        self.options: SearchOptions | None = None

    def search(self, collection, options, query_embedding):
        self.options = options
        assert query_embedding == ([0.0, 1.0] if options.mode != "lexical" else None)
        channels = (
            ("lexical", "semantic") if options.mode == "hybrid" else (options.mode,)
        )
        return [
            SearchHit(
                self.units[1],
                0.031,
                channels,
                {"lexical": 2, "semantic": 1},
                bm25_score=4.2,
                semantic_score=0.91,
            )
        ]

    def grep(self, collection, pattern, limit, regex, case_sensitive):
        return [SearchHit(self.units[0], 1.0, ("grep",), {})]


def _node(node_id: str) -> Node:
    return Node(
        node_id,
        f"{node_id}.node.md",
        None,
        "text",
        node_id,
        "fixture",
        "",
        "raw://fixture.pdf",
        "a" * 64,
        {"pages": [2, 2]},
        None,
        None,
        None,
    )


def _service(tmp_path: Path) -> tuple[ReindexService, str, FakeSearchBackend]:
    root = _node("00000000-0000-0000-0000-000000000001")
    second = _node("00000000-0000-0000-0000-000000000002")
    collection = Collection.create(root)
    collection.status = "ready"
    collection.active_revision = "00000000-0000-0000-0000-000000000099"
    collection.embedding_profile = FakeEmbeddings.name
    collection.nodes[second.id] = second
    collection.units = [
        SearchUnit(
            "first",
            root.id,
            "Network plan Project AB-42 cost 15 Mio EUR",
            "Project AB-42 cost 15 Mio EUR",
            10,
            10,
            1,
            locator=root.locator,
        ),
        SearchUnit(
            "second",
            second.id,
            "Renewable solar expansion target",
            "Solar generation doubles to 160 MW",
            20,
            20,
            1,
            locator=second.locator,
        ),
    ]
    catalog = Catalog()
    catalog.create(collection)
    backend = FakeSearchBackend(collection.units)
    service = ReindexService(catalog, FileStore(tmp_path), FakeEmbeddings(), backend)
    return service, collection.id, backend


def test_search_defaults_to_hybrid_and_applies_ranking_params(tmp_path: Path) -> None:
    service, collection_id, backend = _service(tmp_path)
    app = create_app(service)

    async def request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/v1/search",
                json={
                    "collection_id": collection_id,
                    "query": "renewable capacity",
                    "candidate_limit": 80,
                    "filters": {"kinds": ["text"], "path_prefix": "reports/"},
                    "ranking": {
                        "lexical_weight": 1.2,
                        "semantic_weight": 0.8,
                        "rrf_k": 40,
                        "max_per_node": 2,
                    },
                },
            )

    response = asyncio.run(request())
    assert response.status_code == 200
    assert response.json()["executed_mode"] == "hybrid"
    assert backend.options == SearchOptions(
        query="renewable capacity",
        mode="hybrid",
        limit=10,
        candidate_limit=80,
        kinds=("text",),
        path_prefix="reports/",
        lexical_weight=1.2,
        semantic_weight=0.8,
        rrf_k=40,
        max_per_node=2,
    )


def test_search_response_exposes_component_scores_and_verbatim_evidence(
    tmp_path: Path,
) -> None:
    service, collection_id, _ = _service(tmp_path)
    app = create_app(service)

    async def request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/v1/search",
                json={"collection_id": collection_id, "query": "renewable"},
            )

    response = asyncio.run(request())
    result = response.json()["results"][0]
    assert result["rank"] == 1
    assert result["scores"] == {"bm25": 4.2, "semantic": 0.91}
    assert result["evidence"]["node_id"] == "00000000-0000-0000-0000-000000000002"
    assert "id" not in result["evidence"]
    assert result["evidence"]["excerpt"] == "Solar generation doubles to 160 MW"
    assert result["evidence"]["line_start"] == result["evidence"]["line_end"] == 20
    assert result["evidence"]["locator"] == {"pages": [2, 2]}


def test_search_rejects_invalid_candidate_and_weight_combinations(
    tmp_path: Path,
) -> None:
    service, collection_id, _ = _service(tmp_path)
    app = create_app(service)

    async def request(payload):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/v1/search",
                json={"collection_id": collection_id, "query": "x", **payload},
            )

    assert asyncio.run(request({"limit": 20, "candidate_limit": 10})).status_code == 422
    assert asyncio.run(request({"ranking": {"semantic_weight": 0}})).status_code == 422
    assert asyncio.run(request({"mode": "auto"})).status_code == 422


def test_search_has_no_process_local_fallback(tmp_path: Path) -> None:
    service, collection_id, _ = _service(tmp_path)
    service.search_backend = None
    options = SearchOptions("query", "lexical", 10, 100)

    try:
        service.search(collection_id, options)
    except RuntimeError as error:
        assert "ParadeDB" in str(error)
    else:
        raise AssertionError("search unexpectedly used a process-local fallback")


def test_search_cursor_is_stable_and_bound_to_query(tmp_path: Path) -> None:
    service, collection_id, backend = _service(tmp_path)
    backend.search = lambda collection, options, embedding: [
        SearchHit(unit, 1 / rank, ("lexical",), {"lexical": rank})
        for rank, unit in enumerate(backend.units * 3, 1)
    ]
    app = create_app(service)

    async def request(payload):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/v1/search",
                json={
                    "collection_id": collection_id,
                    "query": "renewable",
                    "mode": "lexical",
                    "limit": 2,
                    "ranking": {"max_per_node": 3},
                    **payload,
                },
            )

    first = asyncio.run(request({}))
    assert first.status_code == 200
    assert [item["rank"] for item in first.json()["results"]] == [1, 2]
    cursor = first.json()["next_cursor"]
    second = asyncio.run(request({"cursor": cursor}))
    assert [item["rank"] for item in second.json()["results"]] == [3, 4]
    changed = asyncio.run(
        request({"cursor": cursor, "ranking": {"max_per_node": 2, "rrf_k": 30}})
    )
    assert changed.status_code == 400
    assert changed.json()["error"]["code"] == "invalid_request"
    assert changed.json()["error"]["request_id"] == changed.headers["X-Request-ID"]


def test_api_uses_structured_validation_errors_and_request_ids(
    tmp_path: Path,
) -> None:
    service, collection_id, _ = _service(tmp_path)
    app = create_app(service)

    async def request(payload, headers=None):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/v1/search", json=payload, headers=headers or {})

    response = asyncio.run(
        request(
            {
                "collection_id": collection_id,
                "query": "solar",
                "unknown_parameter": True,
            },
            {"X-Request-ID": "agent-search-42"},
        )
    )
    assert response.status_code == 422
    assert response.headers["X-Request-ID"] == "agent-search-42"
    assert response.json()["error"]["code"] == "invalid_request"
    assert response.json()["error"]["request_id"] == "agent-search-42"
    assert response.json()["error"]["details"]


def test_openapi_exposes_search_contract_and_example(tmp_path: Path) -> None:
    service, _, _ = _service(tmp_path)
    schema = create_app(service).openapi()

    operation = schema["paths"]["/v1/search"]["post"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert request_schema["$ref"].endswith("/SearchRequest")
    assert operation["responses"]["200"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("/SearchApiResponse")
    status_response = schema["paths"]["/v1/collections/status"]["post"]["responses"][
        "200"
    ]["content"]["application/json"]["schema"]
    assert status_response["$ref"].endswith("/CollectionStatusResponse")
    search_schema = schema["components"]["schemas"]["SearchRequest"]
    assert search_schema["examples"][0]["ranking"]["lexical_weight"] == 0.5
    assert search_schema["additionalProperties"] is False


def test_markdown_chunks_preserve_the_line_containing_the_evidence() -> None:
    body = "# Heading\n\nFirst paragraph.\n\nThe installed photovoltaic capacity rises to 160 MW.\n"
    chunks = _markdown_chunks(body, target_tokens=5, overlap_tokens=1)

    evidence = next(chunk for chunk in chunks if "160 MW" in chunk[0])
    assert evidence[1] <= 5 <= evidence[2]
