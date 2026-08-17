from __future__ import annotations

import re
from typing import Any

LCS_THRESHOLD = 0.80


def compare_sample(sample: dict[str, Any], table: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    physical_total = len(table["rows"])
    if sample["totalPhysicalRows"] != physical_total:
        errors.append(
            f"Physical row count differs: sample={sample['totalPhysicalRows']} parser={physical_total}"
        )
    for row in sample["rows"]:
        physical = row["physicalRow"]
        data_index = physical - 1
        if data_index < 0 or data_index >= len(table["rows"]):
            errors.append(f"Sample physical row {physical} is outside parser output")
            continue
        errors.extend(
            _row_errors(f"Physical row {physical}", row["values"], table["rows"][data_index])
        )
    return errors


def _row_errors(label: str, expected: list[Any], actual: list[Any]) -> list[str]:
    if len(expected) != len(actual):
        return [f"{label} width differs: sample={len(expected)} parser={len(actual)}"]
    errors = []
    for index, (left, right) in enumerate(zip(expected, actual), start=1):
        similarity = lcs_similarity(_normalize(left), _normalize(right))
        if similarity < LCS_THRESHOLD:
            errors.append(
                f"{label} column {index} LCS={similarity:.1%} below 80%; "
                f"sample={_preview(left)!r} parser={_preview(right)!r}"
            )
    return errors


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _preview(value: Any, limit: int = 120) -> str:
    text = _normalize(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def lcs_similarity(left: str, right: str) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    longest = max(len(left), len(right))
    if len(left) < len(right):
        left, right = right, left
    previous = [0] * (len(right) + 1)
    for left_char in left:
        current = [0]
        for index, right_char in enumerate(right, start=1):
            current.append(
                previous[index - 1] + 1
                if left_char == right_char
                else max(previous[index], current[-1])
            )
        previous = current
    return previous[-1] / longest
