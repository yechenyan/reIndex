from __future__ import annotations

from typing import Any

import click

from reindex_cli.errors import ReIndexError


def validate_constraints(
    command: dict[str, Any], parameters: dict[str, Any]
) -> None:
    for constraint in command.get("constraints", []):
        if _violated(constraint, parameters):
            _raise_constraint(constraint)


def _violated(constraint: dict[str, Any], values: dict[str, Any]) -> bool:
    kind = constraint["kind"]
    names = constraint.get("parameters", [])
    present = [_present(values.get(name)) for name in names]
    trigger = _present(values.get(constraint.get("parameter")))
    if kind == "requires":
        return trigger and not all(present)
    if kind == "conflicts":
        return trigger and any(present)
    if kind == "mutually_exclusive":
        return sum(present) > 1
    if kind == "any_present":
        return not any(present)
    if kind == "all_or_none":
        return any(present) and not all(present)
    if kind == "range":
        value = values.get(constraint["parameter"])
        return value < constraint["minimum"] or value > constraint["maximum"]
    raise ValueError(f"unsupported CLI constraint kind: {kind}")


def _present(value: Any) -> bool:
    return value is not None and value is not False


def _raise_constraint(constraint: dict[str, Any]) -> None:
    message = constraint["message"]
    if constraint["error"] == "usage":
        raise click.UsageError(message)
    raise ReIndexError(message)
