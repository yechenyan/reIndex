from __future__ import annotations

from .context import Context
from .io import write_json


def run(context: Context, found: dict, merged: dict) -> dict:
    by_id = {item["findTableId"]: item for item in found["tables"]}
    tables = []
    for index, group in enumerate(merged["tables"]):
        members = []
        identifiers = []
        for item in group["tables"]:
            identifier = item["findTableId"]
            source = {**by_id[identifier], **item}
            source["mergeWithPrevious"] = bool(source.get("mergeWithPrevious", False))
            members.append(source)
            identifiers.append(identifier)
        tables.append(
            {
                "parseTableId": f"table_{index:04d}",
                "findTableIds": identifiers,
                "titleHint": group.get("parseTableHint") or members[0].get("title", ""),
                "tables": members,
                "mergeReason": group.get("reason", ""),
            }
        )
    value = {"version": "pdf-table-5/list-table@1.0", "tables": tables}
    write_json(context.paths.helper_json("listTable.json"), value)
    write_json(context.paths.helper_json("finalTable.json"), {"version": "pdf-table-5/final-table@1.0", "tables": []})
    return value

