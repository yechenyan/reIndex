from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from .context import Context
from .io import read_json, write_json
from .review_diagnostics import csv_profile, empty_data_row_indexes
from .sample_review import compare_sample, validate_sample
from .sample_runtime import load_sample

FORBIDDEN = (
    "sample.py", "sample.json", "sampleconfirmation.json", "summary.json", "review.json", "finaltable.json",
)


def run(context: Context, table_id: str, *, output_dir: Path | None = None) -> dict:
    table_dir = context.paths.table_dir(table_id)
    summary = read_json(table_dir / "summary.json")
    errors = validate_summary(summary)
    if summary and summary.get("skipped"):
        sample_errors, sample = sample_result(table_dir)
        errors.extend(sample_errors)
        if sample.get("mode") != "skip":
            errors.append("skipped table requires sample mode skip")
        review = result(table_id, "skipped", not errors, errors, None, 0, summary)
        write_json(table_dir / "review.json", review)
        return review
    sample_errors, sample = sample_result(table_dir)
    image_table = bool(summary and summary.get("imageTable") is True)
    errors.extend(sample_errors)
    parser = table_dir / "parse.py"
    if not parser.is_file():
        errors.append("parse.py is missing")
        review = result(table_id, "failed", False, errors, None, 0, summary)
        write_json(table_dir / "review.json", review)
        return review
    source_errors = static_parser_checks(parser)
    source_errors.extend(static_strategy_checks(context.paths.strategy))
    errors.extend(source_errors)
    destination = (output_dir or context.paths.output) / f"{table_id}.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(parser), "--table-json", str(table_dir / "table.json"), "--output", str(destination)]
    if source_errors:
        destination.unlink(missing_ok=True)
        completed = subprocess.CompletedProcess(command, 0, "", "")
    else:
        completed = subprocess.run(command, cwd=table_dir, text=True, capture_output=True, check=False)
    if completed.returncode:
        errors.append(f"parse.py exited {completed.returncode}: {completed.stderr[-1200:]}")
    rows, format_errors = (
        ([], ["parse.py execution blocked by static policy"])
        if source_errors else read_csv(destination)
    )
    errors.extend(format_errors)
    format_ok = not format_errors and completed.returncode == 0 and not source_errors
    content_errors, equivalent_matches = [], []
    if sample.get("mode") == "skip" and not image_table:
        errors.append("vector table cannot skip content review")
    if format_ok and not sample_errors and sample.get("mode") == "content" and not image_table:
        content_errors, equivalent_matches = compare_sample(rows, sample)
        errors.extend(content_errors)
    contract_ok = not sample_errors and not validate_summary(summary)
    if format_ok and contract_ok and not content_errors and image_table:
        status, accepted = "format_only", True
    elif format_ok and contract_ok and not content_errors and sample.get("mode") == "content":
        status, accepted = "verified", True
    else:
        status, accepted = "failed", False
    review = result(table_id, status, accepted, errors, destination, len(rows), summary)
    review["formatPassed"] = format_ok
    review["contentPassed"] = status == "verified"
    review["hyphenEquivalentMatches"] = equivalent_matches
    review["csvProfile"] = csv_profile(rows)
    review["stdout"] = completed.stdout[-1200:]
    write_json(table_dir / "review.json", review)
    return review


def validate_summary(summary) -> list[str]:
    if not isinstance(summary, dict):
        return ["summary.json is missing or not an object"]
    required = (
        "title", "classification", "pages", "bboxes", "surroundingText", "imageTable", "skipped",
        "skipReason", "strategy", "sqlFriendly", "extractionDpi", "steps",
    )
    errors = [f"summary.json missing {key}" for key in required if key not in summary]
    typed = {
        "title": str, "classification": str, "pages": list, "bboxes": list, "surroundingText": dict,
        "imageTable": bool, "skipped": bool, "skipReason": str, "strategy": str,
        "sqlFriendly": bool, "extractionDpi": int, "steps": list,
    }
    errors.extend(
        f"summary.json {key} must be {expected.__name__}"
        for key, expected in typed.items() if key in summary and not isinstance(summary[key], expected)
    )
    if isinstance(summary.get("surroundingText"), dict):
        for key in ("before", "after"):
            if not isinstance(summary["surroundingText"].get(key), str):
                errors.append(f"summary.json surroundingText.{key} must be str")
    return errors


def sample_result(table_dir: Path) -> tuple[list[str], dict]:
    errors, sample = load_sample(table_dir)
    if not errors:
        errors.extend(validate_sample(sample))
    return errors, sample


def static_parser_checks(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    return [f"parse.py contains forbidden reference: {name}" for name in FORBIDDEN if name in text]


def static_strategy_checks(strategy_dir: Path) -> list[str]:
    errors = []
    for path in strategy_dir.glob("strategy_*.py"):
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        errors.extend(f"{path.name} contains forbidden reference: {name}" for name in FORBIDDEN if name in text)
    return errors


def read_csv(path: Path) -> tuple[list[list[str]], list[str]]:
    if not path.is_file():
        return [], ["output CSV was not created"]
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
    except Exception as exc:
        return [], [f"cannot read UTF-8 CSV: {exc}"]
    errors = []
    if not rows or not rows[0] or not any(cell.strip() for cell in rows[0]):
        errors.append("CSV header is empty")
    widths = {len(row) for row in rows}
    if len(widths) > 1:
        errors.append(f"inconsistent CSV column counts: {sorted(widths)}")
    if any("\x00" in cell for row in rows for cell in row):
        errors.append("CSV contains NUL characters")
    empty_rows = empty_data_row_indexes(rows)
    if empty_rows:
        errors.append(f"CSV contains entirely empty data rows at indexes {empty_rows}; never pad row counts")
    return rows, errors


def result(table_id: str, status: str, accepted: bool, errors: list[str], output: Path | None, rows: int, summary) -> dict:
    return {
        "version": "pdf-table-5/review@1.0", "parseTableId": table_id, "status": status,
        "accepted": accepted, "errors": errors, "outputPath": str(output) if output else None,
        "rowCount": rows, "title": (summary or {}).get("title", ""),
    }
