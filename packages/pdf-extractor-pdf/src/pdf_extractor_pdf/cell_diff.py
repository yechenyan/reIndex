from __future__ import annotations

import re
import unicodedata


def normalized_values(values: list) -> list[str]:
    return [_normalize(value) for value in values]


def cell_diffs(actual: list, expected: list, columns: list[str]) -> list[dict]:
    diffs = []
    for index in range(max(len(actual), len(expected))):
        raw_actual = actual[index] if index < len(actual) else None
        raw_expected = expected[index] if index < len(expected) else None
        norm_actual, norm_expected = _normalize(raw_actual), _normalize(raw_expected)
        if norm_actual != norm_expected:
            diffs.append({
                "column_index": index, "column": columns[index] if index < len(columns) else None,
                "extractor_raw": raw_actual, "qa_raw": raw_expected,
                "extractor_normalized": norm_actual, "qa_normalized": norm_expected,
                "difference_kind": _difference_kind(raw_actual, raw_expected),
            })
    return diffs


def _difference_kind(left: object, right: object) -> str:
    if left is None or right is None:
        return "missing_cell"
    if _normalize(str(left).replace("\u00ad", "")) == _normalize(str(right).replace("\u00ad", "")):
        return "soft_hyphen"
    dehyphen = lambda value: re.sub(r"-\s+", "", _normalize(value))
    if dehyphen(left) == dehyphen(right):
        return "line_break_hyphen"
    return "value_difference"


def _normalize(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value)).replace("\u00a0", " ")).strip()
