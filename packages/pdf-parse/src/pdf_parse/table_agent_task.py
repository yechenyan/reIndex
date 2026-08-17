from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_cli import AgentError
from .io_utils import atomic_json, read_json, utc_now
from .paths import ProjectPaths
from .state import StateStore
from .table_agent_calls import handle_rerender, table_call
from .table_prep import prepare_table
from .table_records import empty_usage, failed, parsed, replace_usage, skipped
from .table_review import execute_review


def process_table(
    paths: ProjectPaths,
    pdf_path: Path,
    table_id: str,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    params = read_json(paths.params)
    config = params["agents"]
    state = StateStore(paths)
    table_state = state.table(table_id)
    dpi = float(table_state.get("requestedDpi", params["screenshots"]["defaultDpi"]))
    repairs = int(table_state.get("repairs", 0))
    usage = dict(table_state.get("usage") or empty_usage())
    steps: list[dict[str, Any]] = []
    context, images = prepare_table(paths, pdf_path, table_id, candidates, dpi)
    try:
        proposal = table_call(
            paths, context, images, config, table_state.get("agentSessionId")
        )
        replace_usage(usage, proposal.usage)
        state.update_table(
            table_id,
            status="running",
            agentSessionId=proposal.session_id,
            usage=usage,
        )
        if proposal.data["action"] == "rerender":
            proposal, context, images, dpi = handle_rerender(
                paths, pdf_path, table_id, candidates, proposal, context, images, dpi, config, usage
            )
        _validate_proposal(proposal.data, candidates)
        if proposal.data["action"] == "skip":
            state.update_table(table_id, status="skip", requestedDpi=dpi, usage=usage)
            return skipped(table_id, candidates, proposal.data, usage)
        _write_proposal(
            paths, table_id, proposal.data, steps, dpi, context["latestGeometry"]["revision"]
        )
        review = execute_review(paths.blocks / table_id)
        while review["status"] != "pass" and repairs < config["maxRepairsPerTable"]:
            repairs += 1
            steps.append({"at": utc_now(), "type": "review_failed", "errors": review["errors"]})
            proposal = table_call(
                paths,
                context,
                images,
                config,
                proposal.session_id,
                proposal.data,
                review["errors"],
                review["result"],
                review["sample"],
            )
            replace_usage(usage, proposal.usage)
            _validate_proposal(proposal.data, candidates)
            _write_proposal(
                paths,
                table_id,
                proposal.data,
                steps,
                dpi,
                context["latestGeometry"]["revision"],
            )
            review = execute_review(paths.blocks / table_id)
            state.update_table(table_id, repairs=repairs, usage=usage)
        state.update_table(
            table_id,
            status=review["status"],
            repairs=repairs,
            requestedDpi=dpi,
            usage=usage,
        )
        return parsed(table_id, candidates, proposal.data, review, repairs, usage, dpi)
    except (AgentError, ValueError, OSError) as exc:
        state.update_table(table_id, status="failed", repairs=repairs, error=str(exc), usage=usage)
        return failed(table_id, candidates, str(exc), repairs, usage, dpi)


def _validate_proposal(data: dict[str, Any], candidates: list[dict[str, Any]]) -> None:
    if data["action"] == "ready" and (
        not data["samplePy"].strip() or not data["parsePy"].strip()
    ):
        raise ValueError("Ready proposal requires samplePy and parsePy")
    allowed = {item["classifyBlockId"] for item in candidates}
    merged = set(data["mergedClassifyBlockIds"] or [candidates[0]["classifyBlockId"]])
    if candidates[0]["classifyBlockId"] not in merged or not merged.issubset(allowed):
        raise ValueError("Agent returned invalid merged table IDs")


def _write_proposal(paths, table_id, data, steps, dpi, geometry_revision):
    directory = paths.blocks / table_id
    (directory / "sample.py").write_text(data["samplePy"], encoding="utf-8")
    (directory / "parse.py").write_text(data["parsePy"], encoding="utf-8")
    atomic_json(
        directory / "summary.json",
        {
            **data["summary"],
            "resolutionDpi": dpi,
            "geometryRevisionUsed": data["geometryRevisionUsed"],
            "geometryRevisionExpected": geometry_revision,
            "geometryRevisionMatched": data["geometryRevisionUsed"] == geometry_revision,
            "steps": steps,
        },
    )
