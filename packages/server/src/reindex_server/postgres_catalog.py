from __future__ import annotations

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from reindex_server.database import Database
from reindex_server.domain import Collection, Node
from reindex_server.errors import ConflictError
from reindex_server.postgres_current_catalog import PostgresCurrentCatalogMixin
from reindex_server.postgres_records import (
    insert_links,
    insert_nodes,
    insert_resources,
    load_links,
    load_resources,
    node_from_row,
)
from reindex_server.postgres_version_catalog import PostgresVersionCatalogMixin
from reindex_server.postgres_versions import version_from_row


class PostgresCatalog(PostgresCurrentCatalogMixin, PostgresVersionCatalogMixin):
    """PostgreSQL catalog with atomic active-version replacement."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, collection: Collection) -> Collection:
        try:
            with (
                self.database.connection() as connection,
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    """INSERT INTO collections (id, name, status, progress)
                       VALUES (%s, %s, %s, %s)""",
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
                active_version_id=(
                    str(row["active_version_id"]) if row["active_version_id"] else None
                ),
                embedding_profile=row["embedding_profile"],
                progress=row["progress"] or {},
                error=row["error"],
                resources=resources,
            )

    def get_by_name(self, name: str) -> Collection:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT id FROM collections WHERE name = %s", (name,))
            row = cursor.fetchone()
            if row is None:
                raise KeyError("collection not found")
            return self.get(str(row["id"]))

    def list_collections(self) -> list[Collection]:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT * FROM collections ORDER BY name")
            return [
                Collection(
                    id=str(row["id"]),
                    name=row["name"],
                    status=row["status"],
                    package_hash=row["package_hash"],
                    active_version_id=(
                        str(row["active_version_id"])
                        if row["active_version_id"]
                        else None
                    ),
                    embedding_profile=row["embedding_profile"],
                    progress=row["progress"] or {},
                    error=row["error"],
                )
                for row in cursor.fetchall()
            ]

    def current_version(self, collection_id: str):
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT version.* FROM collections AS collection
                   LEFT JOIN collection_versions AS version
                     ON version.id = collection.active_version_id
                   WHERE collection.id = %s""",
                (collection_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return version_from_row(row) if row["id"] is not None else None

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

    def get_node_by_path(self, collection_id: str, path: str) -> Node:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM nodes WHERE collection_id = %s AND path = %s",
                (collection_id, path),
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError("node not found")
            return self.get_node(collection_id, str(row["id"]))

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
                       WHERE collection_id = %s
                         AND parent_node_id IS NOT DISTINCT FROM %s
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
