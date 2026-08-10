from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .context import Context
from .io import write_json


@dataclass
class AgentResult:
    returncode: int
    session_id: str | None
    model: str
    reasoning_effort: str
    token_usage: dict[str, int]
    events_path: Path
    last_message_path: Path
    payload: dict[str, Any] | None


class AgentResumeError(RuntimeError):
    pass


def run_agent(
    context: Context,
    role: str,
    prompt: str,
    *,
    images: list[Path] | None = None,
    output_schema: dict | None = None,
    session_id: str | None = None,
) -> AgentResult:
    log_dir = context.paths.report / "agents"
    log_dir.mkdir(parents=True, exist_ok=True)
    attempt = 1 + len(list(log_dir.glob(f"{role}-*.events.jsonl")))
    stem = f"{role}-{attempt:02d}"
    prompt_path = log_dir / f"{stem}.prompt.md"
    events_path = log_dir / f"{stem}.events.jsonl"
    stderr_path = log_dir / f"{stem}.stderr.log"
    last_path = log_dir / f"{stem}.last.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    schema_path = None
    if output_schema is not None:
        schema_path = log_dir / f"{stem}.output.schema.json"
        write_json(schema_path, output_schema)
    for image in images or []:
        if not image.is_file():
            raise FileNotFoundError(f"Agent image input is missing: {image}")
    command = build_command(context, last_path, schema_path, images or [], session_id=session_id)
    with events_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        completed = subprocess.run(
            command, input=prompt, text=True, stdout=stdout, stderr=stderr,
            cwd=context.paths.project, check=False,
        )
    events = load_events(events_path)
    if completed.returncode:
        tail = stderr_path.read_text(encoding="utf-8", errors="replace")[-2000:]
        error = f"{role} agent failed with exit {completed.returncode}: {tail}"
        raise AgentResumeError(error) if session_id else RuntimeError(error)
    if not has_terminal_event(events):
        error = f"{role} agent ended without a terminal event; inspect {events_path}"
        raise AgentResumeError(error) if session_id else RuntimeError(error)
    payload = load_payload(last_path) if output_schema is not None else None
    return AgentResult(
        returncode=completed.returncode,
        session_id=find_session_id(events) or session_id,
        model=context.codex_model,
        reasoning_effort=context.reasoning_effort,
        token_usage=find_token_usage(events),
        events_path=events_path,
        last_message_path=last_path,
        payload=payload,
    )


def build_command(
    context: Context,
    last_path: Path,
    schema_path: Path | None,
    images: list[Path],
    *,
    session_id: str | None = None,
) -> list[str]:
    if session_id:
        command = ["codex", "exec", "resume"]
    else:
        command = ["codex", "exec"]
    command.extend(["--json", "--ignore-user-config", "--skip-git-repo-check"])
    if not session_id:
        command.extend(["--sandbox", "workspace-write", "--cd", str(context.paths.project.resolve())])
    command.extend(
        [
            "--model", context.codex_model,
            "--config", f'model_reasoning_effort="{context.reasoning_effort}"',
            "--output-last-message", str(last_path),
        ]
    )
    if schema_path is not None:
        command.extend(["--output-schema", str(schema_path)])
    for path in images:
        command.extend(["--image", str(path.resolve())])
    if session_id:
        command.append(session_id)
    command.append("-")
    return command


def load_payload(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Agent did not return structured JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Agent structured output must be an object: {path}")
    return value


def load_events(path: Path) -> list[dict[str, Any]]:
    result = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            result.append(value)
    return result


def find_session_id(events: list[dict]) -> str | None:
    for event in events:
        if event.get("type") in {"thread.started", "session.started"}:
            return event.get("thread_id") or event.get("session_id") or event.get("id")
    return None


def has_terminal_event(events: list[dict]) -> bool:
    return any(event.get("type") in {"turn.completed", "turn.failed"} for event in events)


def find_token_usage(events: list[dict]) -> dict[str, int]:
    best: dict[str, int] = {}
    for event in events:
        for candidate in nested_usage(event):
            normalized = {
                key: int(value) for key, value in candidate.items()
                if "token" in key.lower() and isinstance(value, (int, float))
            }
            if sum(normalized.values()) >= sum(best.values()):
                best = normalized
    return best


def nested_usage(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"usage", "token_usage", "tokenUsage"} and isinstance(child, dict):
                yield child
            yield from nested_usage(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested_usage(child)
