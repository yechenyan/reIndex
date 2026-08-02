from __future__ import annotations

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from reindex_server.database import Database
from reindex_server.domain import Collection, Node, Resource, SearchUnit
from reindex_server.errors import ConflictError
from reindex_server.postgres_projection import (
    progress,
    replace_projection,
    update_collection,
)
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


class PostgresCatalog(PostgresVersionCatalogMixin):
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

    def sync(self, collection: Collection) -> None:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE collections SET status = %s, package_hash = %s,
                   embedding_profile = %s, progress = %s, error = %s,
                   updated_at = now() WHERE id = %s""",
                (
                    collection.status,
                    collection.package_hash,
                    collection.embedding_profile,
                    Jsonb(collection.progress),
                    Jsonb(collection.error) if collection.error else None,
                    collection.id,
                ),
            )

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
            replace_projection(
                cursor, collection.id, nodes, resources, units, embedding_profile
            )
            cursor.execute(
                """UPDATE collections SET name = %s, status = 'ready',
                   package_hash = %s, embedding_profile = %s, progress = %s,
                   error = NULL, updated_at = now() WHERE id = %s""",
                (
                    name,
                    package_hash,
                    embedding_profile,
                    Jsonb(progress(nodes, resources, units, embedding_profile)),
                    collection.id,
                ),
            )
        update_collection(
            collection,
            name,
            nodes,
            resources,
            units,
            embedding_profile,
            package_hash,
        )

    def push_current(
        self,
        *,
        collection_id: str,
        name: str,
        nodes: dict[str, Node],
        resources: dict[tuple[str, str], Resource],
        units: list[SearchUnit],
        embedding_profile: str | None,
        package_hash: str,
    ) -> Collection:
        try:
            with (
                self.database.connection() as connection,
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    "SELECT id FROM collections WHERE name = %s AND id <> %s",
                    (name, collection_id),
                )
                if cursor.fetchone() is not None:
                    raise ConflictError("collection name already exists")
                cursor.execute(
                    """INSERT INTO collections (id, name, status, progress)
                       VALUES (%s, %s, 'draft', '{}'::jsonb)
                       ON CONFLICT (id) DO NOTHING""",
                    (collection_id, name),
                )
        except UniqueViolation as error:
            raise ConflictError("collection name already exists") from error
        collection = self.get(collection_id)
        self.replace_current(
            collection,
            name=name,
            nodes=nodes,
            resources=resources,
            units=units,
            embedding_profile=embedding_profile,
            package_hash=package_hash,
        )
        return collection
