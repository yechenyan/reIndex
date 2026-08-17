from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_cli import AgentResult, run_agent
from .paths import ProjectPaths
from .prompts import compose, load_prompt
from .table_prep import prepare_table
from .table_records import replace_usage


def table_call(
    paths: ProjectPaths,
    context: dict[str, Any],
    images: list[Path],
    config: dict[str, Any],
    session_id: str | None = None,
    current: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    generated_table: dict[str, Any] | None = None,
    visual_sample: dict[str, Any] | None = None,
    rerender_update: bool = False,
) -> AgentResult:
    if errors:
        repair_mode = "visual_recheck" if needs_visual_review(errors) else "code_repair"
        prompt_context = {
            "repairMode": repair_mode,
            "reviewErrors": errors,
            "generatedTable": generated_table,
            "currentVisualSample": visual_sample,
            "geometryRevisionUsed": (current or {}).get("geometryRevisionUsed"),
        }
        prompt_name = "repair.md"
    elif rerender_update:
        prompt_context = {
            "requestedDpi": context["requestedDpi"],
            "dpiBounds": context["dpiBounds"],
            "evidence": context["evidence"],
            "geometryRevision": context["latestGeometry"]["revision"],
        }
        prompt_name = "rerender.md"
    else:
        prompt_context = context
        prompt_name = "table.md"
    prompt = compose(load_prompt("base.md"), load_prompt(prompt_name), context=prompt_context)
    return run_agent(
        project_root=paths.root,
        prompt=prompt,
        images=images if not errors else [],
        schema_name="table.json",
        model=config["model"],
        reasoning=config["reasoningEffort"],
        session_id=session_id,
    )


def handle_rerender(
    paths: ProjectPaths,
    pdf_path: Path,
    table_id: str,
    candidates: list[dict[str, Any]],
    proposal: AgentResult,
    context: dict[str, Any],
    images: list[Path],
    dpi: float,
    config: dict[str, Any],
    usage: dict[str, int],
) -> tuple[AgentResult, dict[str, Any], list[Path], float]:
    for _ in range(2):
        if proposal.data["action"] != "rerender":
            return proposal, context, images, dpi
        requested = proposal.data["requestedDpi"]
        if requested == dpi:
            raise ValueError("Agent requested the already supplied DPI")
        dpi = requested
        context, images = prepare_table(paths, pdf_path, table_id, candidates, dpi)
        proposal = table_call(
            paths, context, images, config, proposal.session_id, rerender_update=True
        )
        replace_usage(usage, proposal.usage)
    if proposal.data["action"] == "rerender":
        raise ValueError("Agent exhausted the screenshot rerender budget")
    return proposal, context, images, dpi


def needs_visual_review(errors: list[str]) -> bool:
    prefixes = ("Header ", "Physical row ", "Sample physical row ")
    return any(error.startswith(prefixes) for error in errors)
