from __future__ import annotations

import re
import unicodedata

from .review_diagnostics import mismatch_message
from .sample_contract import expected_sample_indexes


RULE_KIND = "ignore_space_hyphen"
IGNORED_HYPHENS = "-\u00ad\u2010\u2011"


def validate_sample(sample) -> list[str]:
    if not isinstance(sample, dict) or sample.get("mode") not in {"content", "skip"}:
        return ["sample.py output is missing or has invalid mode"]
    errors = validate_rules(sample.get("compareRules", []))
    if sample.get("mode") == "content":
        errors.extend(validate_content(sample))
    elif (
        sample.get("totalRows") != 0
        or sample.get("header") != []
        or sample.get("rows") != []
        or not sample.get("skipReason")
    ):
        errors.append("skip sample requires totalRows=0, empty header/rows, and skipReason")
    return errors


def validate_content(sample: dict) -> list[str]:
    errors = []
    total_rows = sample.get("totalRows")
    if type(total_rows) is not int or total_rows < 1:
        errors.append("sample totalRows must be a positive integer")
    if not string_list(sample.get("header")) or not isinstance(sample.get("rows"), list):
        return [*errors, "content sample requires header and rows arrays"]
    expected = expected_sample_indexes(total_rows) if type(total_rows) is int else []
    indexes, width = [], len(sample["header"])
    for item in sample["rows"]:
        if not isinstance(item, dict) or type(item.get("rowIndex")) is not int or not string_list(item.get("values")):
            errors.append("sample rows must be {rowIndex:int, values:string[]} objects")
            continue
        indexes.append(item["rowIndex"])
        if len(item["values"]) != width:
            errors.append(f"sample row {item['rowIndex']} has {len(item['values'])} cells; expected {width}")
        if not any(value.strip() for value in item["values"]):
            errors.append(f"sample row {item['rowIndex']} is entirely empty")
    if indexes != expected:
        errors.append(f"sample row indexes must be {expected}, got {indexes}")
    return errors


def validate_rules(rules) -> list[str]:
    if not isinstance(rules, list):
        return ["sample compareRules must be an array"]
    errors = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict) or rule.get("kind") != RULE_KIND:
            errors.append(f"sample compareRules[{index}] has unsupported kind")
            continue
        columns = rule.get("columns")
        if not isinstance(columns, list) or not columns:
            errors.append(f"sample compareRules[{index}].columns must be a non-empty array")
        for field in ("columns", "rowIndexes"):
            value = rule.get(field, [])
            if not isinstance(value, list) or any(type(item) is not int or item < 0 for item in value):
                errors.append(f"sample compareRules[{index}].{field} must be non-negative integers")
    return errors


def compare_sample(rows: list[list[str]], sample: dict) -> tuple[list[str], list[dict]]:
    errors, equivalent = [], []
    if len(rows) != sample["totalRows"]:
        errors.append(f"row count mismatch: expected {sample['totalRows']}, got {len(rows)}")
    if rows:
        compare_row("header", 0, sample["header"], rows[0], sample, errors, equivalent)
    for item in sample["rows"]:
        index, expected = item.get("rowIndex"), item.get("values")
        if not isinstance(index, int) or index < 1 or index >= len(rows):
            errors.append(f"sample rowIndex outside CSV: {index}")
        else:
            compare_row(f"row {index}", index, expected, rows[index], sample, errors, equivalent)
    return errors, equivalent


def compare_row(label, row_index, expected, actual, sample, errors, equivalent) -> None:
    left, right = normalize_row(expected), normalize_row(actual)
    if left == right:
        return
    if len(left) != len(right):
        errors.append(mismatch_message(label, left, right))
        return
    mismatched = []
    for column, (wanted, found) in enumerate(zip(left, right)):
        if wanted == found:
            continue
        explicit = applies(sample.get("compareRules", []), row_index, column)
        if (explicit and hyphen_key(wanted) == hyphen_key(found)) or hyphen_spacing_equal(wanted, found):
            equivalent.append(
                {"rowIndex": row_index, "columnIndex": column, "expected": wanted, "actual": found,
                 "rule": RULE_KIND}
            )
        else:
            mismatched.append(column)
    if mismatched:
        errors.append(mismatch_message(label, left, right))


def applies(rules: list, row_index: int, column: int) -> bool:
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("kind") != RULE_KIND:
            continue
        columns, row_indexes = rule.get("columns", []), rule.get("rowIndexes", [])
        if (not columns or column in columns) and (not row_indexes or row_index in row_indexes):
            return True
    return False


def normalize_row(row) -> list[str]:
    if not isinstance(row, list):
        return []
    return [re.sub(r"\s+", " ", str(cell)).strip() for cell in row]


def hyphen_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(f"[\\s{re.escape(IGNORED_HYPHENS)}]+", "", normalized)


def hyphen_spacing_equal(left: str, right: str) -> bool:
    def key(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value)
        normalized = re.sub(f"[{re.escape(IGNORED_HYPHENS)}]", "-", normalized)
        return re.sub(r"\s*-\s*", "-", normalized)

    return "-" in key(left) and key(left) == key(right)


def string_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)
