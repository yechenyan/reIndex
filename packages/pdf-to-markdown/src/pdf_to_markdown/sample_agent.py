from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .io import write_json


ROW_SCHEMA = {
    "type": "object",
    "properties": {
        "rowIndex": {"type": "integer", "minimum": 1},
        "values": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["rowIndex", "values"],
    "additionalProperties": False,
}
SAMPLE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "samples": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tableId": {"type": "string"},
                    "readable": {"type": "boolean"},
                    "reason": {"type": "string"},
                    "totalRows": {"type": "integer", "minimum": 0},
                    "header": {"type": "array", "items": {"type": "string"}},
                    "rows": {"type": "array", "items": ROW_SCHEMA},
                },
                "required": ["tableId", "readable", "reason", "totalRows", "header", "rows"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["samples"],
    "additionalProperties": False,
}


def run_samples(
    project: Path,
    candidates: list[dict],
    images: dict[str, list[Path]],
    *,
    model: str,
    reasoning_effort: str,
    batch_size: int = 8,
) -> tuple[dict[str, dict], dict[str, int]]:
    pending = [candidate for candidate in candidates if candidate["route"] == "sample"]
    samples: dict[str, dict] = {}
    usage: dict[str, int] = {}
    for batch_index in range(0, len(pending), batch_size):
        batch = pending[batch_index : batch_index + batch_size]
        result, batch_usage = run_batch(
            project,
            batch,
            images,
            model=model,
            reasoning_effort=reasoning_effort,
            batch_number=batch_index // batch_size + 1,
        )
        for sample in result["samples"]:
            samples[sample["tableId"]] = sample
        for key, value in batch_usage.items():
            usage[key] = usage.get(key, 0) + value
    expected = {candidate["tableId"] for candidate in pending}
    if samples.keys() != expected:
        raise ValueError(f"Sample agent returned wrong table IDs: expected {sorted(expected)}, got {sorted(samples)}")
    return samples, usage


def run_batch(project, candidates, images, *, model, reasoning_effort, batch_number):
    agent_dir = project / "artifacts" / "agents"
    agent_dir.mkdir(parents=True, exist_ok=True)
    stem = f"sample-{batch_number:02d}"
    prompt_path = agent_dir / f"{stem}.prompt.md"
    schema_path = agent_dir / f"{stem}.schema.json"
    events_path = agent_dir / f"{stem}.events.jsonl"
    stderr_path = agent_dir / f"{stem}.stderr.log"
    last_path = agent_dir / f"{stem}.last.json"
    attachments, mapping = [], []
    for candidate in candidates:
        numbers = []
        for path in images[candidate["tableId"]]:
            attachments.append(path)
            numbers.append(len(attachments))
        mapping.append({"tableId": candidate["tableId"], "pages": candidate["pages"], "attachments": numbers})
    prompt = sample_prompt(mapping)
    prompt_path.write_text(prompt, encoding="utf-8")
    write_json(schema_path, SAMPLE_SCHEMA)
    command = [
        "codex", "exec", "--json", "--ignore-user-config", "--skip-git-repo-check",
        "--sandbox", "workspace-write", "--cd", str(project.resolve()),
        "--model", model, "--config", f'model_reasoning_effort="{reasoning_effort}"',
        "--output-schema", str(schema_path), "--output-last-message", str(last_path),
    ]
    for path in attachments:
        command.extend(["--image", str(path.resolve())])
    command.append("-")
    with events_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        completed = subprocess.run(command, input=prompt, text=True, stdout=stdout, stderr=stderr, cwd=project)
    if completed.returncode:
        raise RuntimeError(f"Sample agent failed: {stderr_path.read_text(errors='replace')[-2000:]}")
    value = json.loads(last_path.read_text(encoding="utf-8"))
    return value, token_usage(events_path)


def sample_prompt(mapping: list[dict]) -> str:
    return f"""PDF TABLE SOURCE SAMPLING v1

Inspect the attached PDF table crops. They are the only authority; no candidate Markdown values are supplied.
Attachment mapping: {json.dumps(mapping, ensure_ascii=False, separators=(',', ':'))}

For every table, use the top visual row as the Markdown header row, even when the source has no semantic header.
totalRows includes that header. Data rowIndex starts at 1. If there are at most six data rows, return every row;
otherwise return rows 1, 2, 3 and the last three. Preserve blank cells and exact punctuation, numbers, units, case,
and visible line-wrapped cell text joined with single spaces. Never invent obscured values. If the complete table,
its row count, or sampled cells cannot be read reliably, set readable=false, explain why, and return zero/empty
sample fields. Return one structured sample for every mapped tableId.
"""


def token_usage(path: Path) -> dict[str, int]:
    best: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        for candidate in nested_usage(value):
            found = {key: int(item) for key, item in candidate.items() if "token" in key.lower() and isinstance(item, (int, float))}
            if sum(found.values()) > sum(best.values()):
                best = found
    return best


def nested_usage(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"usage", "token_usage", "tokenUsage"} and isinstance(child, dict):
                yield child
            yield from nested_usage(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested_usage(child)
