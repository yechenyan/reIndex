from __future__ import annotations

from psycopg.types.json import Jsonb

from reindex_server.domain import CollectionVersion
from reindex_server.storage import object_key


def version_from_row(row) -> CollectionVersion:
    return CollectionVersion(
        id=str(row["id"]),
        collection_id=str(row["collection_id"]),
        parent_version_id=(
            str(row["parent_version_id"]) if row["parent_version_id"] else None
        ),
        package_hash=row["package_hash"],
        manifest_sha256=row["manifest_sha256"],
        manifest_object_key=row["manifest_object_key"],
        message=row["message"],
        operation=row["operation"],
        source_version_id=(
            str(row["source_version_id"]) if row["source_version_id"] else None
        ),
        created_at=row["created_at"],
        stats=row["stats"] or {},
    )


def insert_version(cursor, version: CollectionVersion) -> None:
    cursor.execute(
        """INSERT INTO collection_versions
           (id, collection_id, parent_version_id, package_hash, manifest_sha256,
            manifest_object_key, message, operation, source_version_id, stats,
            created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            version.id,
            version.collection_id,
            version.parent_version_id,
            version.package_hash,
            version.manifest_sha256,
            version.manifest_object_key,
            version.message,
            version.operation,
            version.source_version_id,
            Jsonb(version.stats),
            version.created_at,
        ),
    )


def insert_version_files(cursor, version_id: str, files: list[dict]) -> None:
    cursor.executemany(
        """INSERT INTO version_files
           (version_id, namespace, logical_path, sha256, byte_size, media_type,
            object_key)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        [
            (
                version_id,
                value["namespace"],
                value["logical_path"],
                value["sha256"],
                value["byte_size"],
                value["media_type"],
                value.get("object_key") or object_key(value["sha256"]),
            )
            for value in files
        ],
    )


def load_version_files(cursor, version_id: str) -> list[dict]:
    cursor.execute(
        """SELECT namespace, logical_path, sha256, byte_size, media_type, object_key
           FROM version_files WHERE version_id = %s
           ORDER BY namespace, logical_path""",
        (version_id,),
    )
    return [dict(row) for row in cursor.fetchall()]
