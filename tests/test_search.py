from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from reindex_server.app import create_app
from reindex_server.catalog import Catalog
from reindex_server.domain import Collection, Node, SearchHit, SearchOptions, SearchUnit
from reindex_server.embeddings import EmbeddingProvider
from reindex_server.reranking import Reranker
from reindex_server.search_fusion import confidence_bonus
from reindex_server.search_projection import markdown_chunks
from reindex_server.service import ReindexService
from reindex_server.storage import FileStore

ROOT_ID = "00000000-0000-0000-0000-000000000001"
SECOND_ID = "00000000-0000-0000-0000-000000000002"


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


class FakeReranker(Reranker):
    name = "test-reranker"
    candidate_limit = 2
    fusion_weight = 0.75

    def rerank(self, query, hits):
        return [
            replace(hit, score=float(index), rerank_score=float(index))
            for index, hit in enumerate(reversed(hits), 1)
        ], 2.5


def _node(node_id: str, parent_id: str | None, order: int | None) -> Node:
    tree = (ROOT_ID,) if parent_id is None else (ROOT_ID, node_id)
    order_path = () if order is None else (order,)
    return Node(
        node_id,
        ROOT_ID,
        f"{node_id}.node.md",
        parent_id,
        order,
        tree,
        order_path,
        "text" if parent_id else "group",
        node_id,
        "fixture",
        "",
        {},
        "a" * 64,
    )


def _service(tmp_path: Path) -> tuple[ReindexService, FakeSearchBackend]:
    root = _node(ROOT_ID, None, None)
    second = _node(SECOND_ID, ROOT_ID, 1)
    units = [
        SearchUnit(
            "first",
            root.id,
            "card",
            "Network plan Project AB-42",
            "Project AB-42",
            10,
            10,
            1,
        ),
        SearchUnit(
            "second",
            second.id,
            "content_text",
            "Renewable solar expansion",
            "Solar generation doubles to 160 MW",
            20,
            20,
            1,
        ),
    ]
    collection = Collection(
        ROOT_ID,
        "fixture",
        status="ready",
        package_hash="a" * 64,
        embedding_profile=FakeEmbeddings.name,
        nodes={root.id: root, second.id: second},
        units=units,
    )
    catalog = Catalog()
    catalog.create(collection)
    backend = FakeSearchBackend(units)
    return ReindexService(
        catalog, FileStore(tmp_path), FakeEmbeddings(), backend
    ), backend


def test_search_applies_ranking_and_subtree_filters(tmp_path: Path) -> None:
    service, backend = _service(tmp_path)
    app = create_app(service)

    async def request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/v1/search",
                json={
                    "collection_id": ROOT_ID,
                    "query": "renewable capacity",
                    "candidate_limit": 80,
                    "filters": {"kinds": ["text"], "subtree_node_id": ROOT_ID},
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
    assert backend.options == SearchOptions(
        query="renewable capacity",
        mode="hybrid",
        limit=10,
        candidate_limit=80,
        kinds=("text",),
        subtree_node_id=ROOT_ID,
        lexical_weight=1.2,
        semantic_weight=0.8,
        rrf_k=40,
        max_per_node=2,
    )


def test_search_response_has_typed_verbatim_evidence(tmp_path: Path) -> None:
    service, _ = _service(tmp_path)
    response = asyncio.run(
        _post(create_app(service), {"collection_id": ROOT_ID, "query": "renewable"})
    )
    result = response.json()["results"][0]
    assert result["scores"] == {
        "bm25": 4.2,
        "semantic": 0.91,
        "rerank": None,
        "rerank_bonus": None,
    }
    assert result["evidence"]["node_id"] == SECOND_ID
    assert result["evidence"]["unit_type"] == "content_text"
    assert result["evidence"]["excerpt"] == "Solar generation doubles to 160 MW"
    assert result["evidence"]["line_start"] == result["evidence"]["line_end"] == 20


def test_search_cursor_is_bound_to_current_package(tmp_path: Path) -> None:
    service, backend = _service(tmp_path)
    backend.search = lambda collection, options, embedding: [
        SearchHit(unit, 1 / rank, ("lexical",), {"lexical": rank})
        for rank, unit in enumerate(backend.units * 3, 1)
    ]
    app = create_app(service)
    first = asyncio.run(
        _post(
            app,
            {
                "collection_id": ROOT_ID,
                "query": "x",
                "mode": "lexical",
                "limit": 2,
                "ranking": {"max_per_node": 3},
            },
        )
    )
    cursor = first.json()["next_cursor"]
    second = asyncio.run(
        _post(
            app,
            {
                "collection_id": ROOT_ID,
                "query": "x",
                "mode": "lexical",
                "limit": 2,
                "cursor": cursor,
                "ranking": {"max_per_node": 3},
            },
        )
    )
    assert [item["rank"] for item in second.json()["results"]] == [3, 4]
    service.catalog.get(ROOT_ID).package_hash = "b" * 64
    stale = asyncio.run(
        _post(
            app,
            {
                "collection_id": ROOT_ID,
                "query": "x",
                "mode": "lexical",
                "limit": 2,
                "cursor": cursor,
                "ranking": {"max_per_node": 3},
            },
        )
    )
    assert stale.status_code == 400


def test_search_reranking_observability(tmp_path: Path) -> None:
    service, backend = _service(tmp_path)
    service.reranker = FakeReranker()
    backend.search = lambda collection, options, embedding: [
        SearchHit(backend.units[0], 0.5, ("lexical",), {}),
        SearchHit(backend.units[1], 0.4, ("lexical",), {}),
    ]
    response = asyncio.run(
        _post(
            create_app(service),
            {
                "collection_id": ROOT_ID,
                "query": "solar",
                "mode": "lexical",
                "ranking": {"max_per_node": 2},
            },
        )
    )
    assert response.json()["reranking"] == {
        "profile": "test-reranker",
        "candidate_limit": 2,
        "reranked_count": 2,
        "latency_ms": 2.5,
        "fusion": "weighted_rrf",
        "weight": 0.75,
        "rrf_k": 60,
    }


def test_invalid_search_and_openapi_contract(tmp_path: Path) -> None:
    service, _ = _service(tmp_path)
    app = create_app(service)
    invalid = asyncio.run(
        _post(
            app,
            {
                "collection_id": ROOT_ID,
                "query": "x",
                "limit": 20,
                "candidate_limit": 10,
            },
        )
    )
    assert invalid.status_code == 422
    schema = app.openapi()
    response_schema = schema["paths"]["/v1/search"]["post"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("/SearchApiResponse")
    assert (
        "revision_id"
        not in schema["components"]["schemas"]["SearchApiResponse"]["properties"]
    )


def test_markdown_chunks_preserve_evidence_line() -> None:
    body = "# Heading\n\nFirst paragraph.\n\nThe installed capacity rises to 160 MW.\n"
    evidence = next(
        chunk for chunk in markdown_chunks(body, 5, 1) if "160 MW" in chunk[0]
    )
    assert evidence[1] <= 5 <= evidence[2]


def test_confidence_bonus_requires_positive_margin() -> None:
    first = SearchUnit("first", ROOT_ID, "card", "", "", None, None, 1)
    second = SearchUnit("second", SECOND_ID, "card", "", "", None, None, 1)
    assert confidence_bonus(
        [
            SearchHit(first, 0, (), {}, rerank_score=3.0),
            SearchHit(second, 0, (), {}, rerank_score=1.0),
        ]
    ) == {"first": 0.0045000000000000005}
    assert (
        confidence_bonus(
            [
                SearchHit(first, 0, (), {}, rerank_score=-1.0),
                SearchHit(second, 0, (), {}, rerank_score=-2.0),
            ]
        )
        == {}
    )


async def _post(app, payload):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/v1/search", json=payload)
