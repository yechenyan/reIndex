from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SENTINEL = "/__pdf_parse_visual_sample_input_must_not_be_read__.json"


def run_visual_sample(path: Path, timeout: int = 120) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        process = subprocess.run(
            [sys.executable, str(path), "--table-json", SENTINEL],
            cwd=path.parent,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, [f"sample.py could not run: {exc}"]
    if process.returncode:
        return None, [f"sample.py exited {process.returncode}: {process.stderr[-1000:]}"]
    try:
        sample = json.loads(process.stdout)
    except json.JSONDecodeError:
        return None, ["sample.py did not emit one JSON object"]
    if not isinstance(sample, dict):
        return None, ["sample.py output must be a JSON object"]
    errors = validate_sample(sample)
    return (sample if not errors else None), errors


def validate_sample(sample: dict[str, Any]) -> list[str]:
    required = {"mode", "rows", "totalPhysicalRows", "compareRules", "skipReason"}
    missing = required - sample.keys()
    if missing:
        return [f"Sample missing keys: {sorted(missing)}"]
    if sample["mode"] not in {"sample", "skip"}:
        return ["Sample mode must be sample or skip"]
    if sample["mode"] == "skip":
        return [] if sample["skipReason"] else ["Skipped sample requires skipReason"]
    errors: list[str] = []
    if not isinstance(sample["totalPhysicalRows"], int) or sample["totalPhysicalRows"] < 1:
        errors.append("Sample totalPhysicalRows must be a positive integer")
    rows = sample["rows"] if isinstance(sample["rows"], list) else []
    if not rows:
        errors.append("Sample requires sampled rows")
    widths: set[int] = set()
    physical_rows: list[int] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("values"), list):
            errors.append("Each sampled row requires physicalRow and values")
            continue
        widths.add(len(row["values"]))
        physical = row.get("physicalRow")
        if not isinstance(physical, int):
            errors.append("Sample physical rows must be integers")
        else:
            physical_rows.append(physical)
    if len(widths) != 1 or 0 in widths:
        errors.append(f"Visual sample is not rectangular; observed widths: {sorted(widths)}")
    if len(physical_rows) != len(set(physical_rows)):
        errors.append("Sample physical rows must be unique")
    if isinstance(sample["totalPhysicalRows"], int) and sample["totalPhysicalRows"] > 0:
        all_rows = list(range(1, sample["totalPhysicalRows"] + 1))
        expected = all_rows if len(all_rows) <= 6 else all_rows[:3] + all_rows[-3:]
        if physical_rows != expected:
            errors.append(f"Sample must contain first/last visual rows {expected}")
    if sample["compareRules"] != []:
        errors.append("Sample compareRules must be an empty array; all cells use LCS")
    return errors
