from __future__ import annotations

from .agent_context import parser_images
from .agent_schemas import SAMPLE_CONFIRM_OUTPUT_SCHEMA
from .agents import run_agent
from .io import write_json
from .prompts_sample import sample_confirmation_prompt
from .sample_gate import changed_locations, raw_sample, raw_sample_changed
from .sample_review import validate_sample
from .sample_runtime import load_sample_source
from .state import recorded_step


def resolve_sample_change(
    context, table_id: str, packet: dict, parser_context: dict, current_source: str,
    proposed_source: str | None, attempt: int,
) -> str | None:
    if proposed_source is None:
        return None
    try:
        proposed = checked_sample(context, table_id, proposed_source, "proposed")
    except ValueError as exc:
        reject_invalid_proposal(context, table_id, attempt, exc)
        return None
    current_error = None
    try:
        current = checked_sample(context, table_id, current_source, "current")
    except ValueError as exc:
        current, current_error = None, str(exc)
    if current is None:
        locations = changed_locations({}, proposed)
        return confirm_from_source(
            context, table_id, packet, parser_context, None, current_source, proposed_source,
            proposed, locations, attempt, current_error,
        )
    if not raw_sample_changed(current, proposed):
        return proposed_source
    locations = changed_locations(current, proposed)
    return confirm_from_source(
        context, table_id, packet, parser_context, current, current_source, proposed_source,
        proposed, locations, attempt, None,
    )


def confirm_from_source(
    context, table_id, packet, parser_context, current, current_source, proposed_source,
    proposed, locations, attempt, current_error,
):
    prompt = sample_confirmation_prompt(parser_context, current, locations, current_error)
    with recorded_step(
        context, f"confirm-sample-{table_id}-{attempt}", {"changedLocations": locations}
    ) as record:
        result = run_agent(
            context, f"sample-confirm-{table_id}", prompt,
            images=parser_images(context, packet), output_schema=SAMPLE_CONFIRM_OUTPUT_SCHEMA,
        )
        record["tokenUsage"] = result.token_usage
        confirmed_source = result.payload["samplePy"]
        try:
            confirmed = checked_sample(context, table_id, confirmed_source, "confirmed")
        except ValueError as exc:
            confirmation = {
                "version": "pdf-table-5/sample-confirmation@1.0",
                "attempt": attempt,
                "decision": "rejected_invalid",
                "reason": result.payload["reason"],
                "changedLocations": locations,
                "errors": [str(exc)],
            }
            write_json(context.paths.table_dir(table_id) / "sampleConfirmation.json", confirmation)
            record["details"].update(decision="rejected_invalid", sessionId=result.session_id)
            return None
        if current is not None and raw_sample(confirmed) == raw_sample(current):
            decision, resolved = "keep_current", current_source
        elif raw_sample(confirmed) == raw_sample(proposed):
            decision, resolved = "accept_proposed", proposed_source
        else:
            decision, resolved = "replace_from_source", confirmed_source
        confirmation = {
            "version": "pdf-table-5/sample-confirmation@1.0",
            "attempt": attempt,
            "decision": decision,
            "reason": result.payload["reason"],
            "changedLocations": locations,
            "confirmedSample": raw_sample(confirmed),
        }
        write_json(context.paths.table_dir(table_id) / "sampleConfirmation.json", confirmation)
        record["details"].update(decision=decision, sessionId=result.session_id)
    return resolved


def reject_invalid_proposal(context, table_id: str, attempt: int, error: ValueError) -> None:
    confirmation = {
        "version": "pdf-table-5/sample-confirmation@1.0",
        "attempt": attempt,
        "decision": "rejected_invalid_proposed",
        "reason": "repair returned a sample.py that cannot run or violates the sample contract",
        "changedLocations": {"metadataFields": [], "rows": []},
        "errors": [str(error)],
    }
    write_json(context.paths.table_dir(table_id) / "sampleConfirmation.json", confirmation)


def checked_sample(context, table_id: str, source: str, label: str) -> dict:
    errors, sample = load_sample_source(context.paths.table_dir(table_id), source)
    errors.extend(validate_sample(sample) if not errors else [])
    if errors:
        raise ValueError(f"{label} samplePy is invalid: {'; '.join(errors)}")
    return sample
