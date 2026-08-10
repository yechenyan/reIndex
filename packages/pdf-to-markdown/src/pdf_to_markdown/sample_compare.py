from __future__ import annotations

import html
import re
import unicodedata


MARKUP = re.compile(r"[*_`]+")


def compare(matrix: list[list[str]], sample: dict) -> dict:
    errors = validate_sample(sample)
    if errors:
        return {"passed": False, "errors": errors}
    if not sample["readable"]:
        return {"passed": False, "errors": [f"source sample unreadable: {sample['reason']}"]}
    if not matrix:
        return {"passed": False, "errors": ["LiteParse table matrix is empty"]}
    if len(matrix) != sample["totalRows"]:
        errors.append(f"row count mismatch: LiteParse={len(matrix)}, source={sample['totalRows']}")
    compare_row("header", matrix[0], sample["header"], errors)
    for item in sample["rows"]:
        index = item["rowIndex"]
        if index >= len(matrix):
            errors.append(f"source row {index} is outside LiteParse table")
        else:
            compare_row(f"row {index}", matrix[index], item["values"], errors)
    return {"passed": not errors, "errors": errors}


def validate_sample(sample: dict) -> list[str]:
    if not isinstance(sample, dict):
        return ["sample is not an object"]
    required = {"readable", "reason", "totalRows", "header", "rows"}
    missing = sorted(required - sample.keys())
    if missing:
        return [f"sample missing fields: {missing}"]
    if not sample["readable"]:
        return []
    total = sample["totalRows"]
    if type(total) is not int or total < 1:
        return ["sample totalRows must be positive"]
    expected = expected_indexes(total)
    indexes = [item.get("rowIndex") for item in sample["rows"] if isinstance(item, dict)]
    return [] if indexes == expected else [f"sample row indexes must be {expected}, got {indexes}"]


def expected_indexes(total_rows: int) -> list[int]:
    data_rows = max(total_rows - 1, 0)
    if data_rows <= 6:
        return list(range(1, data_rows + 1))
    return [1, 2, 3, data_rows - 2, data_rows - 1, data_rows]


def compare_row(label: str, liteparse_row, source_row, errors: list[str]) -> None:
    left = [normalize(value) for value in liteparse_row]
    right = [normalize(value) for value in source_row]
    if left != right:
        errors.append(f"{label} mismatch: LiteParse={left!r}, source={right!r}")


def normalize(value: str) -> str:
    text = html.unescape(str(value)).replace("<br>", " ").replace("<br/>", " ")
    text = unicodedata.normalize("NFC", MARKUP.sub("", text)).replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()
