from __future__ import annotations

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from reindex_server.domain import Collection, Node, Resource, SearchUnit
from reindex_server.errors import ConflictError
from reindex_server.postgres_projection import (
    progress,
    replace_projection,
    update_collection,
)


class PostgresCurrentCatalogMixin:
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
