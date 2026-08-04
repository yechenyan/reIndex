from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Job:
    path: Path
    project_dir: Path
    source: Path
    main: Path
    evidence_dir: Path
    output_dir: Path
    inventory: Path
    reference: Path
    request: str
    evidence: dict[str, Any]
    policy: dict[str, Any]


def load_job(path: Path) -> Job:
    path = path.resolve()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("spec") != "pdf-extractor-pdf/job@1.0":
        raise ValueError("job spec must be pdf-extractor-pdf/job@1.0")
    base = path.parent

    def resolve(key: str, default: str) -> Path:
        value = raw.get(key, default)
        if not isinstance(value, str) or not value:
            raise ValueError(f"job field {key!r} must be a path string")
        return (base / value).resolve()

    source = resolve("source", "../source.pdf")
    if not source.is_file():
        raise FileNotFoundError(source)
    evidence_dir = resolve("evidence_dir", "./evidence")
    return Job(
        path=path,
        project_dir=base.parent,
        source=source,
        main=resolve("main", "./main.py"),
        evidence_dir=evidence_dir,
        output_dir=resolve("output_dir", "../output"),
        inventory=resolve("inventory", "./evidence/inventory.json"),
        reference=resolve("reference", "./evidence/reference.json"),
        request=str(raw.get("request") or "Extract all tables from the PDF."),
        evidence=dict(raw.get("evidence") or {}),
        policy=dict(raw.get("policy") or {}),
    )
