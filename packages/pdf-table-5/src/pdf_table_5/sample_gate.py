from __future__ import annotations


RAW_FIELDS = ("mode", "totalRows", "header", "rows", "skipReason")


def raw_sample(sample: dict) -> dict:
    return {field: sample.get(field) for field in RAW_FIELDS}


def raw_sample_changed(current: dict, proposed: dict) -> bool:
    return raw_sample(current) != raw_sample(proposed)


def changed_locations(current: dict, proposed: dict) -> dict:
    metadata = [
        field for field in ("mode", "totalRows", "skipReason")
        if current.get(field) != proposed.get(field)
    ]
    rows = []
    add_row(rows, 0, current.get("header"), proposed.get("header"))
    before = indexed_rows(current.get("rows"))
    after = indexed_rows(proposed.get("rows"))
    for row_index in sorted(set(before) | set(after)):
        add_row(rows, row_index, before.get(row_index), after.get(row_index))
    return {"metadataFields": metadata, "rows": rows}


def indexed_rows(value) -> dict[int, list[str]]:
    if not isinstance(value, list):
        return {}
    return {
        item["rowIndex"]: item.get("values", [])
        for item in value
        if isinstance(item, dict) and type(item.get("rowIndex")) is int
    }


def add_row(result: list[dict], row_index: int, before, after) -> None:
    if before == after:
        return
    left = before if isinstance(before, list) else []
    right = after if isinstance(after, list) else []
    columns = [
        index for index in range(max(len(left), len(right)))
        if value_at(left, index) != value_at(right, index)
    ]
    result.append({"rowIndex": row_index, "columnIndexes": columns})


def value_at(values: list, index: int):
    return values[index] if index < len(values) else None
