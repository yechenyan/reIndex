from __future__ import annotations

import re
import unicodedata

VALID_COMPARISON_MODES = {"exact", "text"}


def normalized_values(values: list) -> list[str]:
    return [_normalize(value) for value in values]


def validate_modes(value: object, column_count: int) -> list[str]:
    if value is None:
        return ["exact"] * column_count
    if not isinstance(value, list) or len(value) != column_count or any(
        item not in VALID_COMPARISON_MODES for item in value
    ):
        raise ValueError("comparison_modes must contain one exact/text value per column")
    return value


def cell_diffs(actual: list, expected: list, modes: list[str] | None = None) -> list[dict]:
    modes = validate_modes(modes, len(expected))
    diffs = []
    for index in range(max(len(actual), len(expected))):
        raw_actual = actual[index] if index < len(actual) else None
        raw_expected = expected[index] if index < len(expected) else None
        norm_actual, norm_expected = _normalize(raw_actual), _normalize(raw_expected)
        mode = modes[index] if index < len(modes) else "exact"
        content_actual, content_expected = _content_key(raw_actual, mode), _content_key(raw_expected, mode)
        content_equal = raw_actual is not None and raw_expected is not None and content_actual == content_expected
        if raw_actual != raw_expected:
            diffs.append({
                "column_index": index,
                "extractor_raw": raw_actual, "qa_raw": raw_expected,
                "extractor_normalized": norm_actual, "qa_normalized": norm_expected,
                "extractor_content_key": content_actual, "qa_content_key": content_expected,
                "comparison_mode": mode, "raw_equal": False, "content_equal": content_equal,
                "difference_kind": "format_only" if content_equal else _difference_kind(raw_actual, raw_expected),
            })
    return diffs


def blocking_diffs(diffs: list[dict]) -> list[dict]:
    return [item for item in diffs if not item["content_equal"]]


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


def _content_key(value: object, mode: str) -> str:
    normalized = _normalize(value)
    if mode == "exact":
        return normalized
    return "".join(character for character in normalized.casefold() if character.isalnum())
