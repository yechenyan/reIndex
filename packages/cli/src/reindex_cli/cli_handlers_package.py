from __future__ import annotations

from typing import Any

from reindex_cli.collection import resolve_collection
from reindex_cli.pipeline.runner import check_collection, inspect_collection, run_scan


def inspect(parameters: dict[str, Any]) -> dict[str, Any]:
    return inspect_collection(resolve_collection(parameters["path"]))


def scan(parameters: dict[str, Any]) -> dict[str, Any]:
    context = resolve_collection(parameters["path"], parameters["collection_root"])
    return run_scan(context)


def check(parameters: dict[str, Any]) -> dict[str, Any]:
    return check_collection(resolve_collection(parameters["path"]))
