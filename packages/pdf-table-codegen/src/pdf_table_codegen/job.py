from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Job:
    path: Path
    name: str
    source: Path
    extractor: Path
    evidence_dir: Path
    output_dir: Path
    inventory: Path
    reference: Path
    evidence: dict[str, Any]
    policy: dict[str, Any]


def load_job(path: Path) -> Job:
    path = path.resolve()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("spec") != "pdf-table-codegen/job@1.0":
        raise ValueError("job spec must be pdf-table-codegen/job@1.0")
    root = path.parent

    def resolved(key: str, default: str | None = None) -> Path:
        value = raw.get(key, default)
        if not isinstance(value, str) or not value:
            raise ValueError(f"job field {key!r} must be a path string")
        return (root / value).resolve()

    source = resolved("source")
    if not source.is_file():
        raise FileNotFoundError(source)
    evidence_dir = resolved("evidence_dir", "evidence")
    return Job(
        path=path,
        name=str(raw.get("name") or source.stem),
        source=source,
        extractor=resolved("extractor", "extractor.py"),
        evidence_dir=evidence_dir,
        output_dir=resolved("output_dir", "output"),
        inventory=resolved("inventory", "evidence/inventory.frozen.json"),
        reference=resolved("reference", "evidence/visual-reference.json"),
        evidence=dict(raw.get("evidence") or {}),
        policy=dict(raw.get("policy") or {}),
    )
