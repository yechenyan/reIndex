from __future__ import annotations

from psycopg.types.json import Jsonb

from reindex_server.domain import Node, NodeResource, Resource, SearchUnit


def insert_resources(cursor, resources) -> None:
    cursor.executemany(
        """INSERT INTO resources
           (id, collection_id, namespace, logical_path, display_name, sha256, byte_size, media_type, object_key)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (id) DO UPDATE SET sha256 = EXCLUDED.sha256,
             byte_size = EXCLUDED.byte_size, media_type = EXCLUDED.media_type,
             object_key = EXCLUDED.object_key, display_name = EXCLUDED.display_name,
             updated_at = now()""",
        [
            (
                item.id,
                item.collection_id,
                item.namespace,
                item.logical_path,
                item.display_name,
                item.sha256,
                item.byte_size,
                item.media_type,
                item.object_key,
            )
            for item in resources
        ],
    )


def insert_nodes(cursor, nodes) -> None:
    cursor.executemany(
        """INSERT INTO nodes
           (collection_id, id, parent_node_id, ordinal, path, tree_path, order_path,
            kind, title, description, card_markdown, attributes, node_hash)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        [
            (
                item.collection_id,
                item.id,
                item.parent_id,
                item.order,
                item.path,
                list(item.tree_path),
                list(item.order_path),
                item.kind,
                item.title,
                item.description,
                item.card_markdown,
                Jsonb(item.attributes),
                item.node_hash,
            )
            for item in nodes
        ],
    )


def insert_links(cursor, nodes) -> None:
    cursor.executemany(
        """INSERT INTO node_resources
           (collection_id, node_id, role, ordinal, resource_id, locator, asset_role, description)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        [
            (
                node.collection_id,
                node.id,
                link.role,
                link.ordinal,
                link.resource.id,
                Jsonb(link.locator) if link.locator else None,
                link.asset_role,
                link.description,
            )
            for node in nodes
            for link in node.resources
        ],
    )


def insert_units(cursor, collection_id, nodes, units) -> None:
    cursor.executemany(
        """INSERT INTO search_units
           (id, collection_id, node_id, resource_id, unit_type, path, tree_path, kind,
            title, description, ordinal, row_number, start_line, end_line, locator,
            original_text, contextual_text)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        [
            (
                unit.id,
                collection_id,
                unit.node_id,
                unit.resource_id,
                unit.unit_type,
                nodes[unit.node_id].path,
                list(nodes[unit.node_id].tree_path),
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


def load_resources(cursor, collection_id):
    cursor.execute("SELECT * FROM resources WHERE collection_id = %s", (collection_id,))
    result = {}
    for row in cursor.fetchall():
        item = Resource(
            str(row["id"]),
            str(row["collection_id"]),
            row["namespace"],
            row["logical_path"],
            row["display_name"],
            row["sha256"],
            row["byte_size"],
            row["media_type"],
            row["object_key"],
        )
        result[(item.namespace, item.logical_path)] = item
    return result


def load_nodes(cursor, collection_id):
    cursor.execute("SELECT * FROM nodes WHERE collection_id = %s", (collection_id,))
    return {str(row["id"]): node_from_row(row) for row in cursor.fetchall()}


def load_links(cursor, collection_id, nodes, resources, node_id=None):
    by_id = {item.id: item for item in resources.values()}
    if node_id:
        cursor.execute(
            "SELECT * FROM node_resources WHERE collection_id = %s AND node_id = %s ORDER BY role, ordinal",
            (collection_id, node_id),
        )
    else:
        cursor.execute(
            "SELECT * FROM node_resources WHERE collection_id = %s ORDER BY node_id, role, ordinal",
            (collection_id,),
        )
    for row in cursor.fetchall():
        nodes[str(row["node_id"])].resources.append(
            NodeResource(
                row["role"],
                row["ordinal"],
                by_id[str(row["resource_id"])],
                row["locator"],
                row["asset_role"],
                row["description"],
            )
        )


def load_units(cursor, collection_id):
    cursor.execute(
        "SELECT * FROM search_units WHERE collection_id = %s", (collection_id,)
    )
    return [
        SearchUnit(
            row["id"],
            str(row["node_id"]),
            row["unit_type"],
            row["contextual_text"],
            row["original_text"],
            row["start_line"],
            row["end_line"],
            row["ordinal"],
            row["row_number"],
            row["locator"],
            str(row["resource_id"]) if row["resource_id"] else None,
        )
        for row in cursor.fetchall()
    ]


def node_from_row(row) -> Node:
    return Node(
        str(row["id"]),
        str(row["collection_id"]),
        row["path"],
        str(row["parent_node_id"]) if row["parent_node_id"] else None,
        row["ordinal"],
        tuple(map(str, row["tree_path"])),
        tuple(row["order_path"]),
        row["kind"],
        row["title"],
        row["description"],
        row["card_markdown"],
        row["attributes"],
        row["node_hash"],
    )
