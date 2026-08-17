from __future__ import annotations

from pathlib import Path
from typing import Any

from .constants import FORMAT_VERSION, TERMINAL_TABLE_STATES
from .io_utils import atomic_json, read_json, sha256_file, utc_now
from .paths import ProjectPaths
from .sample_guard import run_visual_sample
from .table_review import compare_sample, validate_table


def verify_project(paths: ProjectPaths) -> dict[str, Any]:
    errors = []
    warnings = []
    job = read_json(paths.job)
    if job.get("formatVersion") != FORMAT_VERSION:
        errors.append(f"Project format must be {FORMAT_VERSION}; initialize a fresh project")
    source = Path(job["demand"]["inputPath"])
    if not source.exists() or sha256_file(source) != job["pdfInfo"]["sha256"]:
        errors.append("Source PDF is missing or its SHA-256 changed")
    for required in (paths.output / "output.md", paths.output / "metadata.json"):
        if not required.exists():
            errors.append(f"Missing output: {required}")
    parsed = read_json(paths.helper / "parsedBlocks.json", [])
    for item in parsed:
        if item["status"] not in TERMINAL_TABLE_STATES:
            errors.append(f"Non-terminal table: {item['parseBlockId']}")
        if item["status"] == "pass":
            table_errors = validate_table(item.get("result") or {})
            errors.extend(f"{item['parseBlockId']}: {error}" for error in table_errors)
            asset = paths.assets / f"{item['parseBlockId']}.csv"
            if not asset.exists():
                errors.append(f"Missing table asset: {asset}")
            sample, sample_errors = run_visual_sample(
                paths.blocks / item["parseBlockId"] / "sample.py"
            )
            errors.extend(
                f"{item['parseBlockId']} visual sample: {error}" for error in sample_errors
            )
            if sample is not None:
                errors.extend(
                    f"{item['parseBlockId']}: {error}"
                    for error in compare_sample(sample, item.get("result") or {})
                )
        elif item["status"] in {"failed", "wrong"}:
            warnings.append(f"{item['parseBlockId']} uses LiteParse fallback")
    result = {"verifiedAt": utc_now(), "ok": not errors, "errors": errors, "warnings": warnings}
    atomic_json(paths.report / "verify.json", result)
    return result
