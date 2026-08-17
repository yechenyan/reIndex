from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any


@dataclass
class AgentResult:
    data: dict[str, Any]
    session_id: str
    usage: dict[str, int]
    stderr: str


class AgentError(RuntimeError):
    pass


def run_agent(
    *,
    project_root: Path,
    prompt: str,
    images: list[Path],
    schema_name: str,
    model: str,
    reasoning: str,
    session_id: str | None = None,
    timeout: int = 1200,
) -> AgentResult:
    schema = files("pdf_parse").joinpath("schemas", schema_name)
    with as_file(schema) as schema_path:
        command = _command(
            project_root=project_root,
            schema_path=schema_path,
            images=images,
            model=model,
            reasoning=reasoning,
            session_id=session_id,
        )
        process = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    if process.returncode != 0:
        raise AgentError(f"Codex exited {process.returncode}: {process.stderr[-4000:]}")
    return _parse_events(process.stdout, process.stderr, session_id)


def _command(
    *,
    project_root: Path,
    schema_path: Path,
    images: list[Path],
    model: str,
    reasoning: str,
    session_id: str | None,
) -> list[str]:
    common = [
        "--json",
        "--model",
        model,
        "-c",
        f'model_reasoning_effort="{reasoning}"',
        "--ignore-rules",
        "--skip-git-repo-check",
        "--output-schema",
        str(schema_path),
    ]
    image_args = [part for image in images for part in ("--image", str(image))]
    if session_id:
        return ["codex", "exec", "resume", *common, *image_args, session_id, "-"]
    return [
        "codex",
        "exec",
        "--sandbox",
        "workspace-write",
        "-C",
        str(project_root),
        *common,
        *image_args,
        "-",
    ]


def _parse_events(stdout: str, stderr: str, existing_session: str | None) -> AgentResult:
    session_id = existing_session
    usage: dict[str, int] = {}
    message = None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "thread.started":
            session_id = event.get("thread_id")
        if event.get("type") == "turn.completed":
            usage = event.get("usage") or {}
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            message = item.get("text")
    if not session_id or not message:
        raise AgentError(f"Incomplete Codex JSONL output: {stderr[-4000:]}")
    try:
        data = json.loads(message)
    except json.JSONDecodeError as exc:
        raise AgentError(f"Agent final message is not JSON: {message[:1000]}") from exc
    return AgentResult(data=data, session_id=session_id, usage=usage, stderr=stderr)
