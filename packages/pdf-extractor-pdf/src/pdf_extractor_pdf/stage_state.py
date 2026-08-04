from __future__ import annotations


def require_stage_start_allowed(records: list[dict], run_id: str, agent_id: str | None) -> None:
    if any(item.get("run_id") == run_id for item in records):
        raise ValueError("run_id must be unique")
    terminal = {
        item.get("run_id") for item in records
        if item.get("event") in {"finished", "cancelled"}
    }
    unfinished = [
        item for item in records
        if item.get("event") == "started" and item.get("run_id") not in terminal
    ]
    if agent_id is not None and any(item.get("agent_id") == agent_id for item in unfinished):
        raise ValueError("agent_id already has an unfinished stage")
