from __future__ import annotations

import os
from uuid import uuid4

import pytest
from reindex_server.database import Database
from reindex_server.domain import Collection, Node, SearchOptions, SearchUnit
from reindex_server.paradedb_search import ParadeDBSearch
from reindex_server.postgres import initialize_database
from reindex_server.postgres_catalog import PostgresCatalog

DATABASE_URL = os.getenv("TEST_PARADEDB_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TEST_PARADEDB_URL is not configured"
)


def test_real_current_state_bm25_vector_and_hybrid_search(request) -> None:
    assert DATABASE_URL
    initialize_database(DATABASE_URL)
    database = Database(DATABASE_URL)
    catalog = PostgresCatalog(database)
    backend = ParadeDBSearch(database)
    collection_id = str(uuid4())
    request.addfinalizer(lambda: _cleanup(database, collection_id))
    first_id, second_id = str(uuid4()), str(uuid4())
    root = _node(collection_id, collection_id, None, None, "Energy reports")
    first = _node(
        first_id, collection_id, collection_id, 1, "Transformer expansion AB-42"
    )
    second = _node(second_id, collection_id, collection_id, 2, "Solar capacity")
    nodes = {node.id: node for node in (root, first, second)}
    units = [
        _unit(first, "The AB-42 transformer costs 15 million euros.", _vector(0)),
        _unit(second, "Photovoltaic capacity increases to 160 MW.", _vector(1)),
    ]
    collection = Collection(collection_id, "Energy reports", nodes={root.id: root})
    catalog.create(collection)
    catalog.replace_current(
        collection,
        name="Energy reports",
        nodes=nodes,
        resources={},
        units=units,
        embedding_profile="integration@1024",
        package_hash="a" * 64,
    )

    lexical = backend.search(
        collection, SearchOptions("AB-42 transformer", "lexical", 2, 10), None
    )
    semantic = backend.search(
        collection, SearchOptions("renewable growth", "semantic", 2, 10), _vector(1)
    )
    hybrid = backend.search(
        collection, SearchOptions("transformer growth", "hybrid", 2, 10), _vector(1)
    )
    assert lexical[0].unit.node_id == first_id
    assert lexical[0].bm25_score and lexical[0].bm25_score > 0
    assert semantic[0].unit.node_id == second_id
    assert semantic[0].semantic_score == pytest.approx(1.0)
    assert {channel for hit in hybrid for channel in hit.channels} == {
        "lexical",
        "semantic",
    }

    catalog.replace_current(
        collection,
        name="Energy reports",
        nodes=nodes,
        resources={},
        units=units,
        embedding_profile="integration@1024",
        package_hash="b" * 64,
    )
    loaded = catalog.get(collection_id)
    assert loaded.package_hash == "b" * 64
    assert len(catalog.browse(collection_id, None, True)) == 3
    assert catalog.get_node(collection_id, second_id).title == "Solar capacity"


def _cleanup(database: Database, collection_id: str) -> None:
    with database.connection() as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM collections WHERE id = %s", (collection_id,))
    database.close()


def _node(
    node_id: str,
    collection_id: str,
    parent_id: str | None,
    order: int | None,
    title: str,
) -> Node:
    tree_path = (collection_id,) if parent_id is None else (collection_id, node_id)
    order_path = () if order is None else (order,)
    return Node(
        node_id,
        collection_id,
        f"{node_id}.node.md",
        parent_id,
        order,
        tree_path,
        order_path,
        "group" if parent_id is None else "text",
        title,
        "Fixture document",
        "",
        {},
        "c" * 64,
    )


def _unit(node: Node, text: str, embedding: list[float]) -> SearchUnit:
    return SearchUnit(
        id=f"{node.id}:content_text:1",
        node_id=node.id,
        unit_type="content_text",
        contextual_text=f"{node.title}\n{node.description}\n{text}",
        original_text=text,
        start_line=1,
        end_line=1,
        ordinal=1,
        embedding=embedding,
    )


def _vector(position: int) -> list[float]:
    value = [0.0] * 1024
    value[position] = 1.0
    return value
