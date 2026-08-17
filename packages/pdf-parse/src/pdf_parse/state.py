from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .constants import FORMAT_VERSION
from .io_utils import append_jsonl, atomic_json, read_json, utc_now
from .paths import ProjectPaths


def initial_state(pdf_hash: str) -> dict[str, Any]:
    return {
        "formatVersion": FORMAT_VERSION,
        "pdfHash": pdf_hash,
        "status": "pending",
        "currentStep": None,
        "completedSteps": [],
        "tables": {},
        "agentSessions": {},
        "updatedAt": utc_now(),
    }


class StateStore:
    def __init__(self, paths: ProjectPaths):
        self.paths = paths

    def load(self) -> dict[str, Any]:
        state = read_json(self.paths.states)
        if not isinstance(state, dict):
            raise ValueError("states.json is missing or invalid")
        return state

    def save(self, state: dict[str, Any]) -> None:
        state["updatedAt"] = utc_now()
        atomic_json(self.paths.states, state)

    def completed(self, step: str) -> bool:
        return step in self.load().get("completedSteps", [])

    def table(self, table_id: str) -> dict[str, Any]:
        return self.load().setdefault("tables", {}).get(table_id, {})

    def update_table(self, table_id: str, **values: Any) -> None:
        state = self.load()
        table = state.setdefault("tables", {}).setdefault(table_id, {})
        table.update(values)
        self.save(state)

    @contextmanager
    def step(self, name: str, **details: Any) -> Iterator[dict[str, Any]]:
        state = self.load()
        state["status"] = "running"
        state["currentStep"] = name
        self.save(state)
        event = {
            "id": str(uuid.uuid4()),
            "type": name,
            "createdAt": utc_now(),
            "status": "running",
            **details,
        }
        started = time.perf_counter()
        try:
            yield event
        except Exception as exc:
            event.update(
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
                endedAt=utc_now(),
                durationSeconds=round(time.perf_counter() - started, 3),
            )
            append_jsonl(self.paths.steps, event)
            failed = self.load()
            failed.update(status="failed", currentStep=name, lastError=event["error"])
            self.save(failed)
            raise
        else:
            event.update(
                status="pass",
                endedAt=utc_now(),
                durationSeconds=round(time.perf_counter() - started, 3),
            )
            append_jsonl(self.paths.steps, event)
            passed = self.load()
            done = passed.setdefault("completedSteps", [])
            if name not in done:
                done.append(name)
            passed["currentStep"] = None
            self.save(passed)
