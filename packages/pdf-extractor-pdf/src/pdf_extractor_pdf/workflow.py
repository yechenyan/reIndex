from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pdf_extractor_pdf.artifacts import read_json, write_json

SPEC = "pdf-extractor-pdf/workflow@1.0"
PHASES = ["initialized", "prepared", "inventory_frozen", "inspected", "reference_frozen", "reviewed", "complete"]


def state_path(evidence_dir: Path) -> Path:
    return evidence_dir / "workflow.json"


def load_state(evidence_dir: Path) -> dict[str, Any]:
    path = state_path(evidence_dir)
    if not path.is_file():
        raise FileNotFoundError("workflow is not initialized")
    state = read_json(path)
    if state.get("spec") != SPEC or state.get("phase") not in PHASES:
        raise ValueError("invalid workflow state")
    return state


def require_phase(evidence_dir: Path, *allowed: str) -> dict[str, Any]:
    state = load_state(evidence_dir)
    if state["phase"] not in allowed:
        raise ValueError(f"phase {state['phase']!r} is not one of {allowed!r}")
    return state


def update_phase(evidence_dir: Path, phase: str, event: str, details: dict | None = None) -> dict:
    if phase not in PHASES:
        raise ValueError(f"unknown phase: {phase}")
    path = state_path(evidence_dir)
    current = read_json(path) if path.is_file() else {"spec": SPEC, "history": []}
    now = datetime.now(UTC).isoformat()
    current.update({"phase": phase, "updated_at": now})
    current.setdefault("history", []).append({"event": event, "phase": phase, "at": now, "details": details or {}})
    write_json(path, current)
    return current
