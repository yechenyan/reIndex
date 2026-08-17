from __future__ import annotations

from typing import Any


def parsed(table_id: str, candidates: list[dict[str, Any]], data: dict[str, Any], review: dict[str, Any], repairs: int, usage: dict[str, int], dpi: float) -> dict[str, Any]:
    merged = data["mergedClassifyBlockIds"] or [candidates[0]["classifyBlockId"]]
    sources = [
        source
        for item in candidates
        if item["classifyBlockId"] in merged
        for source in item["sourceBlockIds"]
    ]
    return _base(table_id, merged, sources, review["status"], review["result"], review["errors"], repairs, usage, dpi, data["summary"]["title"], data["summary"]["strategy"])


def skipped(table_id: str, candidates: list[dict[str, Any]], data: dict[str, Any], usage: dict[str, int]) -> dict[str, Any]:
    first = candidates[0]
    return _base(table_id, [first["classifyBlockId"]], first["sourceBlockIds"], "skip", None, data["summary"]["notes"], 0, usage, data["requestedDpi"], data["summary"]["title"], "liteparse-fallback")


def failed(table_id: str, candidates: list[dict[str, Any]], error: str, repairs: int, usage: dict[str, int], dpi: float) -> dict[str, Any]:
    first = candidates[0]
    return _base(table_id, [first["classifyBlockId"]], first["sourceBlockIds"], "failed", None, [error], repairs, usage, dpi, table_id, "liteparse-fallback")


def _base(table_id: str, classify_ids: list[str], source_ids: list[str], status: str, result: Any, errors: list[str], repairs: int, usage: dict[str, int], dpi: float, title: str, strategy: str) -> dict[str, Any]:
    return {"parseBlockId": table_id, "classifyBlockIds": classify_ids, "sourceBlockIds": source_ids, "status": status, "result": result, "errors": errors, "repairs": repairs, "usage": usage, "resolutionDpi": dpi, "title": title, "strategy": strategy}


def empty_usage() -> dict[str, int]:
    return {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0}


def replace_usage(total: dict[str, int], latest: dict[str, int]) -> None:
    total.clear()
    total.update({key: value for key, value in latest.items() if isinstance(value, int)})
