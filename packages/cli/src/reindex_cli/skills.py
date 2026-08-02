from __future__ import annotations

import json
import os
from dataclasses import dataclass
from hashlib import sha256
from importlib.resources import files
from pathlib import Path

from reindex_cli.util import atomic_json

SKILL_NAMES = ("reindex-create", "reindex-scan", "reindex-data")
AGENTS = ("codex", "claude", "cursor", "copilot")


@dataclass(frozen=True)
class SkillResult:
    name: str
    path: str
    status: str


def manage_skills(
    agent: str,
    workspace_root: Path,
    *,
    update: bool,
    force: bool = False,
    codex_home: Path | None = None,
) -> list[SkillResult]:
    if agent not in AGENTS:
        raise ValueError(f"unsupported agent: {agent}")
    home = (
        codex_home or Path(os.getenv("CODEX_HOME", Path.home() / ".codex")).expanduser()
    )
    results = []
    for name in SKILL_NAMES:
        content = _skill_bytes(name)
        for directory in _targets(agent, workspace_root, home, name):
            results.append(_write_skill(name, directory, content, update, force))
    return results


def _write_skill(name, directory, content, update, force):
    target = directory / "SKILL.md"
    marker = directory / ".reindex-managed.json"
    digest = sha256(content).hexdigest()
    if target.is_file():
        current = sha256(target.read_bytes()).hexdigest()
        if current == digest:
            status = "unchanged"
        elif not update:
            status = "conflict"
        elif force or _managed_hash(marker) == current:
            directory.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            status = "updated"
        else:
            status = "conflict"
    else:
        directory.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        status = "installed"
    if status != "conflict":
        atomic_json(marker, {"spec": "reindex/managed-skill@1.0", "sha256": digest})
    return SkillResult(name, str(target), status)


def _managed_hash(marker: Path) -> str | None:
    if not marker.is_file():
        return None
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value.get("sha256") if isinstance(value.get("sha256"), str) else None


def _targets(agent, workspace, codex_home, name):
    if agent == "codex":
        return (
            codex_home / "skills" / name,
            workspace / ".agents" / "skills" / name,
        )
    folder = {"claude": ".claude", "cursor": ".cursor", "copilot": ".copilot"}[agent]
    return (workspace / folder / "skills" / name,)


def _skill_bytes(name: str) -> bytes:
    return (
        files("reindex_cli").joinpath("bundled_skills", name, "SKILL.md").read_bytes()
    )
