from __future__ import annotations

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from reindex_server.database import Database
from reindex_server.domain import Collection, Node, Resource, SearchUnit
from reindex_server.errors import ConflictError
from reindex_server.postgres_records import (
    insert_links,
    insert_nodes,
    insert_resources,
    insert_units,
    load_links,
    load_resources,
    node_from_row,
)


class PostgresCatalog:
    """PostgreSQL current-state catalog; package replacement is one transaction."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, collection: Collection) -> Collection:
        try:
            with (
                self.database.connection() as connection,
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    "INSERT INTO collections (id, name, status, progress) VALUES (%s, %s, %s, %s)",
                    (
                        collection.id,
                        collection.name,
                        collection.status,
                        Jsonb(collection.progress),
                    ),
                )
                insert_resources(cursor, collection.resources.values())
                insert_nodes(cursor, collection.nodes.values())
                insert_links(cursor, collection.nodes.values())
        except UniqueViolation as error:
            raise ConflictError("collection already exists") from error
        return collection

    def get(self, collection_id: str) -> Collection:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT * FROM collections WHERE id = %s", (collection_id,))
            row = cursor.fetchone()
            if row is None:
                raise KeyError("collection not found")
            resources = load_resources(cursor, collection_id)
            return Collection(
                id=str(row["id"]),
                name=row["name"],
                status=row["status"],
                package_hash=row["package_hash"],
                embedding_profile=row["embedding_profile"],
                progress=row["progress"] or {},
                error=row["error"],
                resources=resources,
            )

    def get_node(self, collection_id: str, node_id: str) -> Node:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM nodes WHERE collection_id = %s AND id = %s",
                (collection_id, node_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError("node not found")
            node = node_from_row(row)
            resources = load_resources(cursor, collection_id)
            load_links(cursor, collection_id, {node.id: node}, resources, node.id)
            return node

    def browse(
        self, collection_id: str, parent_node_id: str | None, recursive: bool
    ) -> list[Node]:
        with self.database.connection() as connection, connection.cursor() as cursor:
            if recursive:
                anchor = parent_node_id or collection_id
                cursor.execute(
                    """SELECT * FROM nodes
                       WHERE collection_id = %s AND tree_path @> ARRAY[%s]::uuid[]
                         AND (%s::uuid IS NULL OR id <> %s::uuid)
                       ORDER BY order_path""",
                    (collection_id, anchor, parent_node_id, parent_node_id),
                )
            else:
                cursor.execute(
                    """SELECT * FROM nodes
                       WHERE collection_id = %s AND parent_node_id IS NOT DISTINCT FROM %s
                       ORDER BY ordinal NULLS FIRST""",
                    (collection_id, parent_node_id),
                )
            rows = cursor.fetchall()
            if recursive and parent_node_id and not rows:
                cursor.execute(
                    "SELECT 1 FROM nodes WHERE collection_id = %s AND id = %s",
                    (collection_id, parent_node_id),
                )
                if cursor.fetchone() is None:
                    raise KeyError("parent node not found")
            return [node_from_row(row) for row in rows]

    def sync(self, collection: Collection) -> None:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE collections
                   SET status = %s, package_hash = %s, embedding_profile = %s,
                       progress = %s, error = %s, updated_at = now()
                   WHERE id = %s""",
                (
                    collection.status,
                    collection.package_hash,
                    collection.embedding_profile,
                    Jsonb(collection.progress),
                    Jsonb(collection.error) if collection.error else None,
                    collection.id,
                ),
            )

    def remember_resource(self, resource: Resource) -> None:
        with self.database.connection() as connection, connection.cursor() as cursor:
            insert_resources(cursor, [resource])

    def replace_current(
        self,
        collection: Collection,
        *,
        name: str,
        nodes: dict[str, Node],
        resources: dict[tuple[str, str], Resource],
        units: list[SearchUnit],
        embedding_profile: str | None,
        package_hash: str,
    ) -> None:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (collection.id,),
            )
            cursor.execute(
                "DELETE FROM nodes WHERE collection_id = %s", (collection.id,)
            )
            cursor.execute(
                "DELETE FROM resources WHERE collection_id = %s AND namespace = 'package'",
                (collection.id,),
            )
            insert_resources(cursor, resources.values())
            insert_nodes(cursor, nodes.values())
            insert_links(cursor, nodes.values())
            insert_units(cursor, collection.id, nodes, units)
            if embedding_profile:
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
                    "INSERT INTO search_embeddings (search_unit_id, profile_id, embedding) VALUES (%s, %s, %s)",
                    [
                        (unit.id, embedding_profile, unit.embedding)
                        for unit in units
                        if unit.embedding
                    ],
                )
            cursor.execute(
                """UPDATE collections SET name = %s, status = 'ready', package_hash = %s,
                   embedding_profile = %s, progress = %s, error = NULL, updated_at = now()
                   WHERE id = %s""",
                (
                    name,
                    package_hash,
                    embedding_profile,
                    Jsonb(
                        {
                            "stage": "ready",
                            "nodes": len(nodes),
                            "resources": len(resources),
                            "search_units": len(units),
                            "embedding_profile": embedding_profile,
                        }
                    ),
                    collection.id,
                ),
            )
        collection.name = name
        collection.status = "ready"
        collection.package_hash = package_hash
        collection.embedding_profile = embedding_profile
        collection.progress = {
            "stage": "ready",
            "nodes": len(nodes),
            "resources": len(resources),
            "search_units": len(units),
            "embedding_profile": embedding_profile,
        }
        collection.error = None
        collection.resources, collection.nodes, collection.units = (
            resources,
            nodes,
            units,
        )
