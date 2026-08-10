from __future__ import annotations

import time
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from .context import Context
from .io import append_jsonl, read_json, write_json


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initial_state() -> dict:
    return {
        "version": "pdf-table-5/state@1.0",
        "status": "ready",
        "currentStep": None,
        "currentMergeTableId": -1,
        "currentTableIndex": -1,
        "completedSteps": [],
        "tables": {},
        "lastError": None,
        "updatedAt": utc_now(),
    }


def load_state(context: Context) -> dict:
    return read_json(context.paths.states, initial_state())


def save_state(context: Context, state: dict) -> None:
    state["updatedAt"] = utc_now()
    write_json(context.paths.states, state)


@contextmanager
def recorded_step(context: Context, step_type: str, details: dict | None = None) -> Iterator[dict]:
    state = load_state(context)
    record = {
        "id": str(uuid.uuid4()),
        "type": step_type,
        "createdAt": utc_now(),
        "endedAt": None,
        "durationMs": None,
        "model": context.codex_model,
        "reasoningEffort": context.reasoning_effort,
        "tokenUsage": {},
        "status": "running",
        "details": details or {},
        "error": None,
    }
    state.update(status="running", currentStep={"id": record["id"], "type": step_type})
    save_state(context, state)
    started = time.monotonic()
    try:
        yield record
    except BaseException as exc:
        record["status"] = "failed"
        record["error"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
        state = load_state(context)
        state.update(status="failed", currentStep=None, lastError=record["error"])
        raise
    else:
        record["status"] = "succeeded"
        state = load_state(context)
        completed = state.setdefault("completedSteps", [])
        if step_type not in completed:
            completed.append(step_type)
        state.update(status="running", currentStep=None, lastError=None)
    finally:
        record["endedAt"] = utc_now()
        record["durationMs"] = round((time.monotonic() - started) * 1000)
        append_jsonl(context.paths.steps, record)
        save_state(context, state)
