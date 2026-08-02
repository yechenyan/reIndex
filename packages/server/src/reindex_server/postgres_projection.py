from __future__ import annotations

from psycopg.types.json import Jsonb

from reindex_server.postgres_records import (
    insert_links,
    insert_nodes,
    insert_resources,
    insert_units,
)


def replace_projection(
    cursor,
    collection_id,
    nodes,
    resources,
    units,
    embedding_profile,
) -> None:
    cursor.execute("DELETE FROM nodes WHERE collection_id = %s", (collection_id,))
    cursor.execute("DELETE FROM resources WHERE collection_id = %s", (collection_id,))
    insert_resources(cursor, resources.values())
    insert_nodes(cursor, nodes.values())
    insert_links(cursor, nodes.values())
    insert_units(cursor, collection_id, nodes, units)
    if not embedding_profile:
        return
    vectors = [unit.embedding for unit in units if unit.embedding]
    dimensions = len(vectors[0]) if vectors else 1024
    cursor.execute(
        """INSERT INTO embedding_profiles (id, model, dimensions, config)
           VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING""",
        (
            embedding_profile,
            embedding_profile.split("@", 1)[0],
            dimensions,
            Jsonb({"normalized": True}),
        ),
    )
    cursor.executemany(
        """INSERT INTO search_embeddings
           (search_unit_id, profile_id, embedding) VALUES (%s, %s, %s)""",
        [
            (unit.id, embedding_profile, unit.embedding)
            for unit in units
            if unit.embedding
        ],
    )


def progress(nodes, resources, units, embedding_profile) -> dict:
    return {
        "stage": "ready",
        "nodes": len(nodes),
        "resources": len(resources),
        "search_units": len(units),
        "embedding_profile": embedding_profile,
    }


def update_collection(
    collection,
    name,
    nodes,
    resources,
    units,
    embedding_profile,
    package_hash,
) -> None:
    collection.name = name
    collection.status = "ready"
    collection.package_hash = package_hash
    collection.embedding_profile = embedding_profile
    collection.progress = progress(nodes, resources, units, embedding_profile)
    collection.error = None
    collection.resources, collection.nodes, collection.units = resources, nodes, units
