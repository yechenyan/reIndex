from __future__ import annotations

import os
from uuid import uuid4

import psycopg
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


def test_real_bm25_vector_and_hybrid_search(request) -> None:
    assert DATABASE_URL
    initialize_database(DATABASE_URL)
    database = Database(DATABASE_URL)
    catalog = PostgresCatalog(database)
    backend = ParadeDBSearch(database)
    collection_id = str(uuid4())
    request.addfinalizer(lambda: _cleanup(database, collection_id))
    revision_id = str(uuid4())
    first_id, second_id = str(uuid4()), str(uuid4())
    root = _node(collection_id, "Energy reports", "energy/index.node.md")
    first = _node(first_id, "Transformer expansion AB-42", "energy/transformer.node.md")
    second = _node(second_id, "Solar capacity", "energy/solar.node.md")
    collection = Collection.create(root)
    collection.status = "ready"
    collection.active_revision = revision_id
    collection.embedding_profile = "integration@1024"
    collection.progress = {"embedding_profile": collection.embedding_profile}
    nodes = {node.id: node for node in (root, first, second)}
    units = [
        _unit(first, "The AB-42 transformer costs 15 million euros.", _vector(0)),
        _unit(second, "Photovoltaic capacity increases to 160 MW.", _vector(1)),
    ]

    catalog.create(collection)
    catalog.replace_revision(
        collection, revision_id, nodes, units, collection.embedding_profile
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
    assert hybrid[0].score > 0
    assert {channel for hit in hybrid for channel in hit.channels} == {
        "lexical",
        "semantic",
    }
    for _ in range(8):
        assert backend.search(
            collection,
            SearchOptions("AB-42 transformer", "lexical", 2, 10),
            None,
        )
    second_revision = str(uuid4())
    catalog.replace_revision(
        collection,
        second_revision,
        nodes,
        units,
        collection.embedding_profile,
    )
    collection.active_revision = second_revision
    repeated = backend.search(
        collection, SearchOptions("AB-42 transformer", "lexical", 2, 10), None
    )
    assert repeated[0].unit.id == units[0].id
    with pytest.raises(psycopg.errors.UniqueViolation):
        catalog.replace_revision(
            collection,
            second_revision,
            nodes,
            units,
            collection.embedding_profile,
        )
    assert catalog.get(collection_id).active_revision == second_revision


def _cleanup(database: Database, collection_id: str) -> None:
    with database.connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """DELETE FROM unit_embeddings
               WHERE unit_id IN (
                 SELECT id FROM search_units WHERE collection_id = %s
               )""",
            (collection_id,),
        )
        cursor.execute(
            "DELETE FROM search_units WHERE collection_id = %s", (collection_id,)
        )
        cursor.execute(
            """DELETE FROM nodes
               WHERE revision_id IN (
                 SELECT id FROM collection_revisions WHERE collection_id = %s
               )""",
            (collection_id,),
        )
        cursor.execute(
            "DELETE FROM collection_revisions WHERE collection_id = %s",
            (collection_id,),
        )
        cursor.execute(
            "DELETE FROM collections WHERE root_node_id = %s", (collection_id,)
        )
    database.close()


def _node(node_id: str, title: str, path: str) -> Node:
    return Node(
        node_id,
        path,
        None,
        "text",
        title,
        "Fixture document",
        "",
        None,
        None,
        None,
        None,
        None,
        None,
    )


def _unit(node: Node, text: str, embedding: list[float]) -> SearchUnit:
    return SearchUnit(
        id=f"{node.id}:text:1",
        node_id=node.id,
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
