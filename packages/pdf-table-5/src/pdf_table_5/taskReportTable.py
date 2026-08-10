from __future__ import annotations

import json
import shutil
from pathlib import Path

from .context import Context
from .io import read_json, write_json
from .repair_state import table_snapshot
from .state import utc_now
from .taskReviewTable import run as review_table


def run(context: Context, table_ids: list[str]) -> dict:
    reset_output(context)
    reviews = [safe_review(context, table_id) for table_id in table_ids]
    final_tables = [final_item(context, review) for review in reviews]
    final = {"version": "pdf-table-5/final-table@1.0", "tables": final_tables}
    write_json(context.paths.helper_json("finalTable.json"), final)
    write_json(context.paths.output / "finalTable.json", final)
    steps = read_steps(context.paths.steps)
    token_usage = sum_tokens(steps)
    report = {
        "version": "pdf-table-5/report@1.0",
        "completedAt": utc_now(),
        "accepted": all(item["accepted"] for item in reviews),
        "tableCount": len(reviews),
        "statusCounts": counts(reviews),
        "tokenUsage": token_usage,
        "models": report_models(context, steps),
        "reasoningEfforts": sorted({step.get("reasoningEffort", context.reasoning_effort) for step in steps}),
        "durationMs": sum(int(step.get("durationMs") or 0) for step in steps),
        "tables": reviews,
        "failedTables": [failed_item(context, item) for item in reviews if not item["accepted"]],
    }
    write_json(context.paths.report / "report.json", report)
    (context.paths.report / "report.md").write_text(markdown(report), encoding="utf-8")
    return report


def safe_review(context: Context, table_id: str) -> dict:
    try:
        return review_table(context, table_id)
    except Exception as exc:
        return {
            "version": "pdf-table-5/review@1.0",
            "parseTableId": table_id,
            "title": "",
            "status": "failed",
            "accepted": False,
            "errors": [f"{type(exc).__name__}: {exc}"],
            "outputPath": None,
            "rowCount": 0,
        }


def refresh_metrics(context: Context, report: dict) -> dict:
    steps = read_steps(context.paths.steps)
    report["tokenUsage"] = sum_tokens(steps)
    report["durationMs"] = sum(int(step.get("durationMs") or 0) for step in steps)
    write_json(context.paths.report / "report.json", report)
    (context.paths.report / "report.md").write_text(markdown(report), encoding="utf-8")
    return report


def reset_output(context: Context) -> None:
    target = context.paths.output.resolve()
    project = context.paths.project.resolve()
    if target.name != "output" or target.parent != project:
        raise ValueError(f"Refusing to reset unsafe output path: {target}")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir()


def final_item(context: Context, review: dict) -> dict:
    table_id = review["parseTableId"]
    packet = read_json(context.paths.table_dir(table_id) / "table.json", {})
    summary = read_json(context.paths.table_dir(table_id) / "summary.json", {})
    surrounding = summary.get("surroundingText", {})
    if not isinstance(surrounding, dict):
        surrounding = {}
    return {
        "parseTableId": table_id,
        "title": review.get("title", ""),
        "status": review["status"],
        "accepted": review["accepted"],
        "outputPath": review.get("outputPath"),
        "tables": [
            {"page": item["page"], "bbox": item["bbox"], "imageTable": summary.get("imageTable") is True}
            for item in packet.get("tables", [])
        ],
        "textBefore": summary.get("textBefore", surrounding.get("before", "")),
        "textAfter": summary.get("textAfter", surrounding.get("after", "")),
        "errors": review.get("errors", []),
    }


def failed_item(context: Context, review: dict) -> dict:
    table_id = review["parseTableId"]
    packet = read_json(context.paths.table_dir(table_id) / "table.json", {})
    state = table_snapshot(context, table_id)
    return {
        "parseTableId": table_id,
        "title": review.get("title", ""),
        "pages": [item.get("page") for item in packet.get("tables", [])],
        "attemptsUsed": state.get("repairAttemptsStarted", 0),
        "lastErrors": review.get("errors", []),
        "agentLogDirectory": str((context.paths.report / "agents").resolve()),
        "outputPath": review.get("outputPath"),
    }


def read_steps(path: Path) -> list[dict]:
    result = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            result.append(value)
    return result


def sum_tokens(steps: list[dict]) -> dict[str, int]:
    result: dict[str, int] = {}
    for step in steps:
        for key, value in step.get("tokenUsage", {}).items():
            if isinstance(value, int):
                result[key] = result.get(key, 0) + value
    return result


def report_models(context: Context, steps: list[dict]) -> list[str]:
    fallback = context.codex_model
    values = {step.get("model") for step in steps if step.get("model") not in {None, "codex-config-default"}}
    if any(step.get("model") in {None, "codex-config-default"} for step in steps):
        values.add(fallback)
    return sorted(values)


def counts(reviews: list[dict]) -> dict[str, int]:
    result = {name: 0 for name in ("verified", "format_only", "skipped", "failed")}
    for review in reviews:
        result[review["status"]] = result.get(review["status"], 0) + 1
    return result


def markdown(report: dict) -> str:
    lines = ["# PDF table extraction report", "", f"- Accepted: {report['accepted']}", f"- Tables: {report['tableCount']}"]
    lines.extend(f"- {key}: {value}" for key, value in report["statusCounts"].items())
    lines.extend([f"- Duration (ms): {report['durationMs']}", f"- Token usage: `{report['tokenUsage']}`", "", "## Tables", ""])
    for item in report["tables"]:
        lines.append(f"- `{item['parseTableId']}`: {item['status']} ({item.get('title', '')})")
        lines.extend(f"  - {error}" for error in item.get("errors", []))
    if report.get("failedTables"):
        lines.extend(["", "## Failed tables", ""])
        for item in report["failedTables"]:
            lines.append(f"- `{item['parseTableId']}` after {item['attemptsUsed']} repairs")
            lines.extend(f"  - {error}" for error in item.get("lastErrors", []))
    return "\n".join(lines) + "\n"
