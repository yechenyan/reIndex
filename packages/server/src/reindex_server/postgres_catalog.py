from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from psycopg.types.json import Jsonb

from reindex_server.database import Database
from reindex_server.domain import Collection, Node, SearchUnit


class PostgresCatalog:
    """PostgreSQL source of truth for revisions and retrieval projections."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, collection: Collection) -> Collection:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO collections (root_node_id, root_node, status, progress) VALUES (%s, %s, %s, %s)",
                (
                    collection.id,
                    Jsonb(_node_record(collection.root_node)),
                    collection.status,
                    Jsonb(collection.progress),
                ),
            )
        return collection

    def get(self, collection_id: str) -> Collection:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM collections WHERE root_node_id = %s", (collection_id,)
            )
            record = cursor.fetchone()
            if record is None:
                raise KeyError("collection not found")
            root = _node_from_record(record["root_node"])
            collection = Collection(
                id=str(record["root_node_id"]),
                root_node=root,
                status=record["status"],
                active_revision=str(record["active_revision_id"])
                if record["active_revision_id"]
                else None,
                embedding_profile=self._embedding_profile(
                    cursor, record["active_revision_id"]
                ),
                progress=record["progress"] or {},
                error=record["error"],
                raw=self._raw(cursor, collection_id),
                nodes=self._nodes(cursor, record["active_revision_id"]),
            )
            return collection

    def sync(self, collection: Collection) -> None:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE collections SET status = %s, active_revision_id = %s, progress = %s, error = %s WHERE root_node_id = %s",
                (
                    collection.status,
                    collection.active_revision,
                    Jsonb(collection.progress),
                    Jsonb(collection.error) if collection.error else None,
                    collection.id,
                ),
            )

    def remember_raw(
        self, collection_id: str, raw_path: str, sha256: str, path: Path
    ) -> None:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO blobs (sha256, byte_size, media_type, object_key) VALUES (%s, %s, %s, %s) ON CONFLICT (sha256) DO NOTHING",
                (sha256, path.stat().st_size, "application/octet-stream", str(path)),
            )
            cursor.execute(
                "INSERT INTO raw_files (collection_id, raw_path, sha256) VALUES (%s, %s, %s) ON CONFLICT (collection_id, raw_path) DO UPDATE SET sha256 = EXCLUDED.sha256",
                (collection_id, raw_path, sha256),
            )

    def replace_revision(
        self,
        collection: Collection,
        revision_id: str,
        nodes: dict[str, Node],
        units: list[SearchUnit],
        profile: str | None,
    ) -> None:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO collection_revisions (id, collection_id, status, embedding_profile) VALUES (%s, %s, 'ready', %s)",
                (revision_id, collection.id, profile),
            )
            cursor.executemany(
                """INSERT INTO nodes (revision_id, node_id, parent_node_id, path, kind, title, description, body, source_uri, source_sha256, locator, resource_uri, resource_key, table_meta)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    (
                        revision_id,
                        node.id,
                        node.parent_id,
                        node.path,
                        node.kind,
                        node.title,
                        node.description,
                        node.body,
                        node.source_uri,
                        node.source_sha256,
                        Jsonb(node.locator) if node.locator else None,
                        node.resource_uri,
                        node.resource_key,
                        Jsonb(node.table) if node.table else None,
                    )
                    for node in nodes.values()
                ],
            )
            if profile:
                cursor.execute(
                    "INSERT INTO embedding_profiles (id, model, dimensions, config) VALUES (%s, %s, 1024, %s) ON CONFLICT (id) DO NOTHING",
                    (profile, profile.split("@", 1)[0], Jsonb({"normalized": True})),
                )
            cursor.executemany(
                """INSERT INTO search_units
                   (id, unit_id, collection_id, revision_id, node_id, path, kind, title, description,
                    ordinal, row_number, start_line, end_line, locator, original_text, contextual_text)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    (
                        _search_key(revision_id, unit.id),
                        unit.id,
                        collection.id,
                        revision_id,
                        unit.node_id,
                        nodes[unit.node_id].path,
                        nodes[unit.node_id].kind,
                        nodes[unit.node_id].title,
                        nodes[unit.node_id].description,
                        unit.ordinal,
                        unit.row,
                        unit.start_line,
                        unit.end_line,
                        Jsonb(unit.locator) if unit.locator else None,
                        unit.original_text,
                        unit.contextual_text,
                    )
                    for unit in units
                ],
            )
            if profile:
                cursor.executemany(
                    "INSERT INTO unit_embeddings (unit_id, profile_id, embedding) VALUES (%s, %s, %s)",
                    [
                        (_search_key(revision_id, unit.id), profile, unit.embedding)
                        for unit in units
                        if unit.embedding
                    ],
                )
            cursor.execute(
                "UPDATE collections SET status = %s, active_revision_id = %s, progress = %s, error = NULL WHERE root_node_id = %s",
                (
                    collection.status,
                    revision_id,
                    Jsonb(collection.progress),
                    collection.id,
                ),
            )

    @staticmethod
    def _raw(cursor, collection_id: str) -> dict[str, str]:
        cursor.execute(
            "SELECT raw_path, sha256 FROM raw_files WHERE collection_id = %s",
            (collection_id,),
        )
        return {row["raw_path"]: row["sha256"] for row in cursor.fetchall()}

    @staticmethod
    def _nodes(cursor, revision_id) -> dict[str, Node]:
        if not revision_id:
            return {}
        cursor.execute("SELECT * FROM nodes WHERE revision_id = %s", (revision_id,))
        return {
            str(row["node_id"]): _node_from_record(row) for row in cursor.fetchall()
        }

    @staticmethod
    def _embedding_profile(cursor, revision_id) -> str | None:
        if not revision_id:
            return None
        cursor.execute(
            "SELECT embedding_profile FROM collection_revisions WHERE id = %s",
            (revision_id,),
        )
        record = cursor.fetchone()
        return record["embedding_profile"] if record else None


def _node_record(node: Node) -> dict:
    return asdict(node)


def _search_key(revision_id: str, unit_id: str) -> str:
    return f"{revision_id}:{unit_id}"


def _node_from_record(record: dict) -> Node:
    return Node(
        id=str(record["id"] if "id" in record else record["node_id"]),
        path=record["path"],
        parent_id=str(record["parent_id"])
        if record.get("parent_id")
        else (str(record["parent_node_id"]) if record.get("parent_node_id") else None),
        kind=record["kind"],
        title=record["title"],
        description=record["description"],
        body=record["body"],
        source_uri=record.get("source_uri"),
        source_sha256=record.get("source_sha256"),
        locator=record.get("locator"),
        resource_uri=record.get("resource_uri"),
        resource_key=record.get("resource_key"),
        table=record.get("table") if "table" in record else record.get("table_meta"),
    )
