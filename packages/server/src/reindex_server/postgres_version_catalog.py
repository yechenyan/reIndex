from __future__ import annotations

from datetime import datetime

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from reindex_server.domain import CollectionVersion
from reindex_server.errors import ConflictError, StaleBaseError
from reindex_server.postgres_projection import progress, replace_projection
from reindex_server.postgres_versions import (
    insert_version,
    insert_version_files,
    load_version_files,
    version_from_row,
)


class PostgresVersionCatalogMixin:
    database: object

    def get_version(self, collection_id: str, version_id: str) -> CollectionVersion:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM collection_versions
                   WHERE collection_id = %s AND id = %s""",
                (collection_id, version_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError("version not found")
            return version_from_row(row)

    def list_versions(
        self,
        collection_id: str,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[CollectionVersion]:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM collections WHERE id = %s", (collection_id,))
            if cursor.fetchone() is None:
                raise KeyError("collection not found")
            cursor.execute(
                """SELECT * FROM collection_versions
                   WHERE collection_id = %s
                     AND (%s::timestamptz IS NULL OR created_at < %s)
                   ORDER BY created_at DESC, id DESC LIMIT %s""",
                (collection_id, before, before, limit),
            )
            return [version_from_row(row) for row in cursor.fetchall()]

    def list_all_versions(self) -> list[CollectionVersion]:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM collection_versions ORDER BY created_at DESC, id DESC"
            )
            return [version_from_row(row) for row in cursor.fetchall()]

    def get_version_files(self, collection_id: str, version_id: str) -> list[dict]:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT 1 FROM collection_versions
                   WHERE collection_id = %s AND id = %s""",
                (collection_id, version_id),
            )
            if cursor.fetchone() is None:
                raise KeyError("version not found")
            return load_version_files(cursor, version_id)

    def publish_version(
        self,
        *,
        version: CollectionVersion,
        base_version_id: str | None,
        name: str,
        nodes,
        resources,
        units,
        embedding_profile: str | None,
        manifest_files: list[dict],
    ):
        if any(node.collection_id != version.collection_id for node in nodes.values()):
            raise ConflictError("version Collection does not match projection")
        if any(
            resource.collection_id != version.collection_id
            for resource in resources.values()
        ):
            raise ConflictError("version Collection does not match resources")
        try:
            with (
                self.database.connection() as connection,
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (version.collection_id,),
                )
                cursor.execute(
                    "SELECT * FROM collection_versions WHERE id = %s", (version.id,)
                )
                existing = cursor.fetchone()
                if existing is not None:
                    if version_from_row(existing) != version:
                        raise ConflictError("version ID already exists")
                else:
                    self._insert_published_version(
                        cursor,
                        version,
                        base_version_id,
                        name,
                        nodes,
                        resources,
                        units,
                        embedding_profile,
                        manifest_files,
                    )
        except UniqueViolation as error:
            raise ConflictError("Collection or version already exists") from error
        collection = self.get(version.collection_id)
        collection.resources, collection.nodes, collection.units = (
            resources,
            nodes,
            units,
        )
        return collection

    def _insert_published_version(
        self,
        cursor,
        version,
        base_version_id,
        name,
        nodes,
        resources,
        units,
        embedding_profile,
        manifest_files,
    ) -> None:
        cursor.execute(
            "SELECT active_version_id FROM collections WHERE id = %s FOR UPDATE",
            (version.collection_id,),
        )
        collection_row = cursor.fetchone()
        head = (
            str(collection_row["active_version_id"])
            if collection_row and collection_row["active_version_id"]
            else None
        )
        if head != base_version_id:
            raise StaleBaseError(base_version_id, head)
        if version.parent_version_id != head:
            raise ConflictError("version parent does not match current head")
        cursor.execute(
            "SELECT id FROM collections WHERE name = %s AND id <> %s",
            (name, version.collection_id),
        )
        if cursor.fetchone() is not None:
            raise ConflictError("collection name already exists")
        if collection_row is None:
            cursor.execute(
                """INSERT INTO collections (id, name, status, progress)
                   VALUES (%s, %s, 'draft', '{}'::jsonb)""",
                (version.collection_id, name),
            )
        if version.source_version_id:
            cursor.execute(
                """SELECT 1 FROM collection_versions
                   WHERE id = %s AND collection_id = %s""",
                (version.source_version_id, version.collection_id),
            )
            if cursor.fetchone() is None:
                raise ConflictError("source version does not belong to Collection")
        insert_version(cursor, version)
        insert_version_files(cursor, version.id, manifest_files)
        replace_projection(
            cursor,
            version.collection_id,
            nodes,
            resources,
            units,
            embedding_profile,
        )
        cursor.execute(
            """UPDATE collections SET name = %s, status = 'ready', package_hash = %s,
               active_version_id = %s, embedding_profile = %s, progress = %s,
               error = NULL, updated_at = now() WHERE id = %s""",
            (
                name,
                version.package_hash,
                version.id,
                embedding_profile,
                Jsonb(progress(nodes, resources, units, embedding_profile)),
                version.collection_id,
            ),
        )

    def get_cached_embeddings(
        self, profile_id: str, text_sha256s
    ) -> dict[str, list[float]]:
        digests = list(text_sha256s)
        if not digests:
            return {}
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT text_sha256, embedding FROM embedding_cache
                   WHERE profile_id = %s
                     AND text_sha256::text = ANY(%s::text[])""",
                (profile_id, digests),
            )
            rows = cursor.fetchall()
            cursor.execute(
                """UPDATE embedding_cache SET last_used_at = now()
                   WHERE profile_id = %s
                     AND text_sha256::text = ANY(%s::text[])""",
                (profile_id, digests),
            )
            return {
                row["text_sha256"]: _embedding_list(row["embedding"]) for row in rows
            }

    def put_cached_embeddings(
        self, profile_id: str, values: dict[str, list[float]]
    ) -> None:
        if not values:
            return
        dimensions = len(next(iter(values.values())))
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO embedding_profiles (id, model, dimensions, config)
                   VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING""",
                (
                    profile_id,
                    profile_id.split("@", 1)[0],
                    dimensions,
                    Jsonb({"normalized": True}),
                ),
            )
            cursor.executemany(
                """INSERT INTO embedding_cache (profile_id, text_sha256, embedding)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (profile_id, text_sha256) DO UPDATE
                   SET embedding = EXCLUDED.embedding, last_used_at = now()""",
                [
                    (profile_id, digest, embedding)
                    for digest, embedding in values.items()
                ],
            )

    def prune_versions(
        self,
        collection_id: str,
        *,
        keep_last: int,
        keep_newer_than: datetime,
    ) -> list[CollectionVersion]:
        if keep_last < 0:
            raise ValueError("keep_last must be non-negative")
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (collection_id,),
            )
            cursor.execute(
                "SELECT active_version_id FROM collections WHERE id = %s FOR UPDATE",
                (collection_id,),
            )
            collection = cursor.fetchone()
            if collection is None:
                raise KeyError("collection not found")
            cursor.execute(
                """SELECT * FROM collection_versions WHERE collection_id = %s
                   ORDER BY created_at DESC, id DESC""",
                (collection_id,),
            )
            versions = [version_from_row(row) for row in cursor.fetchall()]
            retained = {value.id for value in versions[:keep_last]}
            retained.update(
                value.id for value in versions if value.created_at >= keep_newer_than
            )
            if collection["active_version_id"]:
                retained.add(str(collection["active_version_id"]))
            removed = [value for value in versions if value.id not in retained]
            if removed:
                cursor.execute(
                    "DELETE FROM collection_versions WHERE id = ANY(%s::uuid[])",
                    ([value.id for value in removed],),
                )
            return removed


def _embedding_list(value) -> list[float]:
    return value.to_list() if hasattr(value, "to_list") else list(value)
