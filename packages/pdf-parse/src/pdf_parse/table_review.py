from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .io_utils import atomic_json
from .sample_guard import run_visual_sample, validate_sample
from .table_compare import compare_sample


def execute_review(table_dir: Path, timeout: int = 120) -> dict[str, Any]:
    parse_path = table_dir / "parse.py"
    sample_path = table_dir / "sample.py"
    errors: list[str] = []
    execution_failed = False

    parse_syntax = _syntax_error(parse_path)
    sample_syntax = _syntax_error(sample_path)
    errors.extend(filter(None, [parse_syntax, sample_syntax]))
    execution_failed = bool(parse_syntax or sample_syntax)

    parsed = None
    if not parse_syntax:
        parsed, parse_errors = _run_json(
            [sys.executable, str(parse_path), "--context", str(table_dir / "preTable.json")],
            table_dir,
            timeout,
        )
        errors.extend(parse_errors)
        execution_failed = execution_failed or bool(parse_errors)

    sample = None
    if not sample_syntax:
        sample, sample_errors = run_visual_sample(sample_path, timeout)
        errors.extend(sample_errors)
        execution_failed = execution_failed or bool(sample_errors)

    table_errors = validate_table(parsed) if parsed is not None else []
    errors.extend(table_errors)
    if parsed is not None and sample is not None and not table_errors:
        errors.extend(compare_sample(sample, parsed))

    status = "pass" if not errors else ("failed" if execution_failed else "wrong")
    review = {"status": status, "errors": errors, "result": parsed, "sample": sample}
    if parsed is not None:
        atomic_json(table_dir / "result.json", parsed)
    if sample is not None:
        atomic_json(table_dir / "sample.json", sample)
    atomic_json(table_dir / "review.json", review)
    return review


def _syntax_error(path: Path) -> str | None:
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        return f"{path.name} syntax error: {exc}"
    return None


def _run_json(
    command: list[str], cwd: Path, timeout: int
) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        process = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, [f"parse.py could not run: {exc}"]
    if process.returncode:
        return None, [f"parse.py exited {process.returncode}: {process.stderr[-2000:]}"]
    try:
        value = json.loads(process.stdout)
    except json.JSONDecodeError:
        return None, ["parse.py did not emit one JSON object"]
    if not isinstance(value, dict):
        return None, ["parse.py output must be a JSON object"]
    return value, []


def validate_table(table: dict[str, Any]) -> list[str]:
    rows = table.get("rows")
    if not isinstance(rows, list):
        return ["Parser output requires a rows array"]
    errors: list[str] = []
    if not rows:
        errors.append("Parser returned no data rows")
    widths: set[int] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, list):
            errors.append(f"Data row {index} is not an array")
            continue
        widths.add(len(row))
        if not any(str(value or "").strip() for value in row):
            errors.append(f"Data row {index} is entirely empty")
        bad = [column for column, value in enumerate(row) if not _scalar(value)]
        errors.extend(f"Data row {index} column {column + 1} is not scalar" for column in bad)
    if len(widths) != 1 or 0 in widths:
        errors.append(f"Table is not rectangular; observed widths: {sorted(widths)}")
    return errors


def _scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float)) or value is None
