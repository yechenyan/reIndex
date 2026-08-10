from __future__ import annotations

import re
from pathlib import Path

from .context import Context
from .io import read_json, write_json
STRATEGY_NAME = re.compile(r"strategy_[a-zA-Z0-9_]+\.py\Z")


ARTIFACT_KEYS = ("samplePy", "summary", "parsePy", "strategyFileName", "strategyPy")


def decode_parser_payload(payload: dict, *, image_table: bool) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Parser output must be an object")
    artifacts = {key: payload.get(key) for key in ARTIFACT_KEYS}
    if not isinstance(artifacts["summary"], dict):
        raise ValueError("Parser summary must be an object")
    for key in ("samplePy", "parsePy", "strategyFileName", "strategyPy"):
        if not isinstance(artifacts[key], str):
            raise ValueError(f"Parser {key} must be a string")
    artifacts["summary"] = {**artifacts["summary"], "imageTable": image_table}
    return artifacts


def merge_repair_payload(current_artifacts: dict, payload: dict, *, revision: int, image_table: bool) -> dict:
    if not isinstance(payload, dict) or payload.get("baseRevision") != revision:
        raise ValueError(f"Repair patch is stale; expected artifact revision {revision}")
    changes = payload.get("changes")
    if not isinstance(changes, dict):
        raise ValueError("Repair changes must be an object")
    unknown = set(changes) - set(ARTIFACT_KEYS)
    if unknown:
        raise ValueError(f"Repair returned unknown artifact fields: {sorted(unknown)}")
    merged = dict(current_artifacts)
    for key in ARTIFACT_KEYS:
        if changes.get(key) is not None:
            merged[key] = changes[key]
    return decode_parser_payload(merged, image_table=image_table)


decode_payload = decode_parser_payload


def apply(context: Context, table_id: str, artifacts: dict, *, sample_archive: int | None = None) -> None:
    table_dir = context.paths.table_dir(table_id)
    sample_py, summary = artifacts["samplePy"], artifacts["summary"]
    if not sample_py.strip():
        raise ValueError("samplePy is required")
    sample_path = table_dir / "sample.py"
    previous_sample = read_text(sample_path)
    if sample_archive is not None and previous_sample and previous_sample != sample_py:
        (table_dir / f"sample{sample_archive}.py").write_text(previous_sample, encoding="utf-8")
    sample_path.write_text(sample_py, encoding="utf-8")
    write_json(table_dir / "summary.json", summary)
    parser = table_dir / "parse.py"
    if summary.get("skipped"):
        parser.unlink(missing_ok=True)
        return
    if not artifacts["parsePy"].strip():
        raise ValueError("parsePy is required for a non-skipped table")
    write_strategy(context.paths.strategy, artifacts)
    parser.write_text(artifacts["parsePy"], encoding="utf-8")


def write_strategy(directory: Path, artifacts: dict) -> None:
    name, source = artifacts["strategyFileName"], artifacts["strategyPy"]
    if not name:
        if source.strip():
            raise ValueError("strategyPy requires strategyFileName")
        return
    if not STRATEGY_NAME.fullmatch(name) or Path(name).name != name:
        raise ValueError(f"Unsafe strategy filename: {name}")
    target = directory / name
    if source.strip():
        if target.exists() and target.read_text(encoding="utf-8") != source:
            raise ValueError(f"Refusing to overwrite existing strategy: {name}")
        target.write_text(source, encoding="utf-8")
    elif not target.is_file():
        raise ValueError(f"Selected strategy does not exist: {name}")


def current(context: Context, table_id: str) -> dict:
    table_dir = context.paths.table_dir(table_id)
    summary = read_json(table_dir / "summary.json", {})
    strategy_name = current_strategy_name(summary)
    strategy_path = context.paths.strategy / strategy_name
    return {
        "samplePy": read_text(table_dir / "sample.py"),
        "summary": summary,
        "parsePy": read_text(table_dir / "parse.py"),
        "strategyFileName": strategy_name if strategy_path.is_file() else "",
        "strategyPy": read_text(strategy_path),
    }


def current_strategy_name(summary: dict) -> str:
    """Return only strategy names that are safe to pass to pathlib."""
    strategy = summary.get("strategy", "") if isinstance(summary, dict) else ""
    if not isinstance(strategy, str):
        return ""
    name = strategy if strategy.endswith(".py") else f"{strategy}.py" if strategy else ""
    return name if STRATEGY_NAME.fullmatch(name) and Path(name).name == name else ""


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
