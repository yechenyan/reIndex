from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Iterator
from uuid import uuid4

from pdf_extractor_pdf.artifacts import append_jsonl, write_json

STAGES = {
    "clarification", "prepare", "discovery", "inventory", "inspection",
    "extraction", "qa", "validation", "review", "finalize", "reporting",
}


@contextmanager
def measure(evidence_dir: Path | None, command: str) -> Iterator[dict]:
    started_at = datetime.now(UTC)
    started = perf_counter()
    record = {"command": command, "started_at": started_at.isoformat(), "ok": False}
    try:
        yield record
        record["ok"] = True
    except Exception as error:
        record["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        record["ended_at"] = datetime.now(UTC).isoformat()
        record["elapsed_seconds"] = round(perf_counter() - started, 6)
        if evidence_dir:
            append_jsonl(evidence_dir / "metrics" / "commands.jsonl", record)


def record_agent(evidence_dir: Path, payload: dict) -> Path:
    required = {"role", "model", "started_at", "ended_at", "conversation_turns"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"agent metric missing fields: {missing}")
    usage = payload.get("token_usage")
    if usage is not None and not isinstance(usage, dict):
        raise ValueError("token_usage must be an object or null")
    path = evidence_dir / "metrics" / "agents.jsonl"
    append_jsonl(path, {"spec": "pdf-extractor-pdf/agent-metric@1.0", **payload})
    return path


def start_stage(
    evidence_dir: Path, stage: str, role: str, model: str,
    run_id: str | None = None, agent_id: str | None = None, workflow_phase: str | None = None,
    table_ids: list[str] | None = None,
) -> dict:
    if stage not in STAGES:
        raise ValueError(f"unknown stage: {stage}")
    record = {
        "spec": "pdf-extractor-pdf/stage-event@1.0", "event": "started",
        "run_id": run_id or str(uuid4()), "stage": stage, "role": role,
        "model": model, "agent_id": agent_id, "workflow_phase": workflow_phase,
        "table_ids": sorted(set(table_ids)) if table_ids else None,
        "at": datetime.now(UTC).isoformat(),
    }
    append_jsonl(evidence_dir / "metrics" / "stages.jsonl", record)
    return record


def finish_stage(evidence_dir: Path, run_id: str, status: str, **details) -> dict:
    if status not in {"completed", "failed", "blocked"}:
        raise ValueError("stage status must be completed, failed, or blocked")
    records = _jsonl(evidence_dir / "metrics" / "stages.jsonl")
    starts = [item for item in records if item.get("run_id") == run_id and item.get("event") == "started"]
    finishes = [item for item in records if item.get("run_id") == run_id and item.get("event") == "finished"]
    if len(starts) != 1 or finishes:
        raise ValueError("run_id must identify one unfinished stage")
    ended = datetime.now(UTC)
    elapsed = max(0.0, (ended - datetime.fromisoformat(starts[0]["at"])).total_seconds())
    waiting = float(details.pop("waiting_seconds", 0) or 0)
    details.pop("conversation_turns", None)
    details.pop("repair_rounds", None)
    if waiting < 0 or waiting > elapsed + 0.01:
        raise ValueError("waiting_seconds must be between zero and elapsed wall time")
    prior = [item for item in records if item.get("event") == "finished"
             and item.get("agent_id") == starts[0].get("agent_id") and item.get("role") == starts[0].get("role")]
    record = {
        **starts[0], "event": "finished", "status": status, "at": ended.isoformat(),
        "started_at": starts[0]["at"], "ended_at": ended.isoformat(),
        "wall_seconds": round(elapsed, 6), "waiting_seconds": round(waiting, 6),
        "active_seconds": round(max(0.0, elapsed - waiting), 6), **details,
        "conversation_turns": 1, "repair_rounds": int(bool(prior)),
        "dispatch_ordinal": len(prior) + 1,
    }
    append_jsonl(evidence_dir / "metrics" / "stages.jsonl", record)
    return record


def metrics_report(evidence_dir: Path) -> dict:
    commands = _jsonl(evidence_dir / "metrics" / "commands.jsonl")
    stages = [item for item in _jsonl(evidence_dir / "metrics" / "stages.jsonl") if item.get("event") == "finished"]
    agents = _dedupe_agents(_jsonl(evidence_dir / "metrics" / "agents.jsonl"))
    by_command: dict[str, dict] = {}
    for item in commands:
        bucket = by_command.setdefault(item["command"], {"calls": 0, "failures": 0, "elapsed_seconds": 0.0})
        bucket["calls"] += 1
        bucket["failures"] += int(not item.get("ok"))
        bucket["elapsed_seconds"] = round(bucket["elapsed_seconds"] + float(item.get("elapsed_seconds", 0)), 6)
    report = {
        "spec": "pdf-extractor-pdf/metrics-summary@1.0",
        "commands": {"total_calls": len(commands), "by_command": by_command},
        "stages": stages,
        "stage_totals": {
            "runs": len(stages),
            "summed_wall_seconds": round(sum(float(item.get("wall_seconds", 0)) for item in stages), 6),
            "parallel_envelope_seconds": _stage_envelope(stages),
            "active_seconds": round(sum(float(item.get("active_seconds", 0)) for item in stages), 6),
            "waiting_seconds": round(sum(float(item.get("waiting_seconds", 0)) for item in stages), 6),
            "conversation_turns": sum(int(item.get("conversation_turns", 0)) for item in stages),
            "repair_rounds": sum(int(item.get("repair_rounds", 0)) for item in stages),
        },
        "agent_runs": agents,
        "token_usage": _token_summary(stages or agents),
    }
    write_json(evidence_dir / "metrics" / "summary.json", report)
    return report


def finished_stages(evidence_dir: Path) -> list[dict]:
    return [item for item in _jsonl(evidence_dir / "metrics" / "stages.jsonl") if item.get("event") == "finished"]


def _jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    import json
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _dedupe_agents(records: list[dict]) -> list[dict]:
    values = {}
    for item in records:
        key = (item.get("role"), item.get("model"), item.get("started_at"))
        values[key] = item
    return list(values.values())


def _token_summary(records: list[dict]) -> dict:
    usages = [item.get("token_usage") for item in records]
    available = [item for item in usages if isinstance(item, dict)]
    keys = {key for item in available for key in item if isinstance(item[key], (int, float))}
    return {
        "available_runs": len(available), "unavailable_runs": len(usages) - len(available),
        "totals": {key: sum(item.get(key, 0) for item in available) for key in sorted(keys)},
    }


def _stage_envelope(records: list[dict]) -> float:
    if not records:
        return 0.0
    starts = [datetime.fromisoformat(item["started_at"]) for item in records]
    ends = [datetime.fromisoformat(item["ended_at"]) for item in records]
    return round(max(0.0, (max(ends) - min(starts)).total_seconds()), 6)
