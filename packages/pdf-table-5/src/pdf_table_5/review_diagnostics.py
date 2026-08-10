from __future__ import annotations

import re


def csv_profile(rows: list[list[str]]) -> dict:
    data = rows[1:] if rows else []
    return {
        "rowCount": len(rows),
        "dataRowCount": len(data),
        "columnCount": len(rows[0]) if rows else 0,
        "emptyDataRowIndexes": empty_data_row_indexes(rows),
        "firstCellHead": first_cells(data[:3], 1),
        "firstCellTail": first_cells(data[-6:], max(1, len(data) - 5)),
    }


def empty_data_row_indexes(rows: list[list[str]]) -> list[int]:
    return [index for index, row in enumerate(rows[1:], start=1) if not any(cell.strip() for cell in row)]


def cross_row_leakage_errors(rows: list[list[str]]) -> list[str]:
    errors = []
    for row_index, (current, following) in enumerate(zip(rows[1:], rows[2:]), start=1):
        for column, (left, right) in enumerate(zip(current, following)):
            reason = leakage_reason(left, right)
            if reason:
                errors.append(f"probable cross-row leakage at row {row_index}, column {column}: {reason}")
    return errors


def leakage_reason(left: str, right: str) -> str | None:
    left_words, right_words = words(left), words(right)
    if not left_words or not right_words or normalized(left) == normalized(right):
        return None
    if re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]{2,}-$", left.strip()) and re.match(r"^[a-zà-öø-ÿ]{2,}\b", right.strip()):
        return f"hyphenated suffix {left_words[-1]!r} continues as {right_words[0]!r}"
    for width in range(min(3, len(left_words), len(right_words)), 0, -1):
        suffix, prefix = left_words[-width:], right_words[:width]
        if suffix != prefix or len(left_words) <= width:
            continue
        if suffix[0] in left_words[:-width]:
            return f"current-row suffix repeats next-row prefix {' '.join(prefix)!r}"
    return None


def words(value: str) -> list[str]:
    return re.findall(r"\w+(?:[-/]\w+)*-?", normalized(value))


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def mismatch_message(label: str, expected, actual) -> str:
    if not isinstance(expected, list) or not isinstance(actual, list):
        return f"{label} mismatch: expected {expected!r}, got {actual!r}"
    differences = []
    width = max(len(expected), len(actual))
    for index in range(width):
        left = expected[index] if index < len(expected) else "<missing>"
        right = actual[index] if index < len(actual) else "<missing>"
        if left != right:
            differences.append(f"c{index}: {short(left)!r} != {short(right)!r}")
    shown = "; ".join(differences[:4])
    suffix = f"; {len(differences) - 4} more" if len(differences) > 4 else ""
    return f"{label} mismatch ({len(differences)} cells): {shown}{suffix}"


def first_cells(rows: list[list[str]], start: int) -> list[list[object]]:
    return [[start + offset, short(row[0] if row else "")] for offset, row in enumerate(rows)]


def short(value, limit: int = 96) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"
