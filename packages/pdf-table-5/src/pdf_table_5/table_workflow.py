from __future__ import annotations

from .agent_context import parser_images, parser_input
from .agent_schemas import PARSER_OUTPUT_SCHEMA, REPAIR_OUTPUT_SCHEMA
from .agents import AgentResumeError, run_agent
from .context import Context
from .io import read_json
from .parser_artifacts import apply, current, decode_parser_payload, merge_repair_payload
from .prompts_parser import parser_prompt, repair_prompt
from .repair_state import begin_repair, complete_repair, record_fallback, record_parser, table_snapshot
from .sample_confirmation import resolve_sample_change
from .state import recorded_step
from .taskReviewTable import run as review_table


def ensure_parser(context: Context, table_id: str, packet: dict) -> dict[str, int]:
    table_dir = context.paths.table_dir(table_id)
    summary = read_json(table_dir / "summary.json")
    ready = isinstance(summary, dict) and (summary.get("skipped") or (table_dir / "parse.py").is_file())
    ready = ready and (table_dir / "sample.py").is_file()
    if ready:
        table_snapshot(context, table_id)
        return {}
    prompt_context = parser_input(context, packet)
    result = run_agent(
        context,
        f"parser-{table_id}",
        parser_prompt(prompt_context),
        images=parser_images(context, packet),
        output_schema=PARSER_OUTPUT_SCHEMA,
    )
    image_table = prompt_context["runtimeClassification"]["imageTable"]
    apply(context, table_id, decode_parser_payload(result.payload, image_table=image_table))
    record_parser(context, table_id, result.session_id)
    return result.token_usage


def review_with_repairs(context: Context, table_id: str) -> dict:
    table_dir = context.paths.table_dir(table_id)
    while True:
        state = table_snapshot(context, table_id)
        review_index = int(state["repairAttemptsCompleted"]) + 1
        with recorded_step(context, f"review-{table_id}-{review_index}") as record:
            review = review_table(context, table_id)
            record["details"].update(status=review["status"], errors=review["errors"])
        if review["accepted"]:
            return review
        pending = begin_repair(context, table_id, context.max_repairs)
        if pending is None:
            return review
        attempt, state = pending
        packet = read_json(table_dir / "table.json", {})
        prompt_context = parser_input(context, packet)
        artifacts = current(context, table_id)
        confirmation = read_json(table_dir / "sampleConfirmation.json", {})
        repair_review = {**review, "sampleSourceConfirmation": confirmation} if confirmation else review
        result, _ = run_repair(
            context, table_id, packet, prompt_context, artifacts, repair_review, attempt, state
        )
        changes = result.payload.get("changes", {})
        if isinstance(changes, dict):
            changes["samplePy"] = resolve_sample_change(
                context, table_id, packet, prompt_context, artifacts["samplePy"],
                changes.get("samplePy"), attempt,
            )
        image_table = prompt_context["runtimeClassification"]["imageTable"]
        merged = merge_repair_payload(
            artifacts, result.payload, revision=int(state["artifactRevision"]), image_table=image_table
        )
        apply(context, table_id, merged, sample_archive=attempt)
        complete_repair(context, table_id, result.session_id)


def run_repair(context, table_id, packet, prompt_context, artifacts, review, attempt, state):
    session_id = state.get("parserSessionId")
    prompt = repair_prompt(
        prompt_context, artifacts, review, attempt, int(state["artifactRevision"]),
        include_full_context=not bool(session_id),
    )
    with recorded_step(context, f"repair-{table_id}-{attempt}") as record:
        try:
            result = run_agent(
                context, f"repair-{table_id}", prompt, images=parser_images(context, packet),
                output_schema=REPAIR_OUTPUT_SCHEMA, session_id=session_id,
            )
            mode = "resumed" if session_id else "new"
        except AgentResumeError as exc:
            record_fallback(context, table_id, str(exc))
            fallback = repair_prompt(
                prompt_context, artifacts, review, attempt, int(state["artifactRevision"]),
                include_full_context=True,
            )
            result = run_agent(
                context, f"repair-{table_id}", fallback, images=parser_images(context, packet),
                output_schema=REPAIR_OUTPUT_SCHEMA,
            )
            mode = "fallback-new"
        record["tokenUsage"] = result.token_usage
        changes = result.payload.get("changes", {}) if isinstance(result.payload, dict) else {}
        changed = sorted(key for key, value in changes.items() if value is not None)
        record["details"].update(sessionMode=mode, sessionId=result.session_id, changedArtifacts=changed)
    return result, mode
