from __future__ import annotations


def expected_sample_indexes(total_rows: int) -> list[int]:
    data_rows = max(total_rows - 1, 0)
    if data_rows <= 6:
        return list(range(1, data_rows + 1))
    return [1, 2, 3, data_rows - 2, data_rows - 1, data_rows]


def normalize_sample_rows(sample: dict) -> dict:
    """Deterministically trim/reorder a valid superset without changing evidence values."""
    if sample.get("mode") != "content" or type(sample.get("totalRows")) is not int:
        return sample
    rows = sample.get("rows")
    if not isinstance(rows, list):
        return sample
    by_index = {}
    for item in rows:
        if not isinstance(item, dict) or type(item.get("rowIndex")) is not int:
            return sample
        by_index.setdefault(item["rowIndex"], item)
    expected = expected_sample_indexes(sample["totalRows"])
    if not all(index in by_index for index in expected):
        return sample
    return {**sample, "rows": [by_index[index] for index in expected]}
