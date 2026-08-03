from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from reindex_cli.parsers.profiles import infer_type


def build_table_profile(
    headers: list[str], rows: list[list[str]]
) -> list[dict[str, Any]]:
    profiles = []
    total = len(rows)
    for index, name in enumerate(headers):
        values = [row[index].strip() for row in rows]
        present = [value for value in values if value]
        value_type = infer_type(present)
        profile: dict[str, Any] = {
            "name": name,
            "type": value_type,
            "non_empty_count": len(present),
            "missing_count": total - len(present),
            "missing_rate": (total - len(present)) / total if total else 0.0,
            "unique_count": len(set(present)),
        }
        if value_type in {"integer", "decimal"} and present:
            numeric = [_decimal(value) for value in present]
            if all(value is not None for value in numeric):
                exact = [value for value in numeric if value is not None]
                profile["min"] = _number(min(exact))
                profile["max"] = _number(max(exact))
        profiles.append(profile)
    return profiles


def table_columns(profile: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "name": value["name"],
            "type": value["type"],
            "description": f"Values recorded in the {value['name']} column.",
        }
        for value in profile
    ]


def _decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", "."))
    except InvalidOperation:
        return None


def _number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)
