from __future__ import annotations

import json

from .agent_context import merge_images
from .agent_schemas import MERGE_OUTPUT_SCHEMA
from .agents import run_agent
from .context import Context
from .contracts import validate_merge_tables
from .io import read_json, relative, write_json
from .pdf import render_page
from .prompts_finder import merge_prompt


def run(context: Context, found: dict) -> tuple[dict, dict[str, int]]:
    possible = [item for item in found["tables"] if item["mergeWithPrevious"] == "possible"]
    packet = prepare(context, found, possible)
    output = context.paths.helper_json("mergeTable.json")
    identifiers = {item["findTableId"] for item in found["tables"]}
    if output.exists():
        try:
            return validate_merge_tables(read_json(output), identifiers), {}
        except ValueError:
            pass
    decisions = {}
    usage: dict[str, int] = {}
    if possible:
        result = run_agent(
            context,
            "merge",
            merge_prompt(packet),
            images=merge_images(context, packet),
            output_schema=MERGE_OUTPUT_SCHEMA,
        )
        decision_document = json.loads(result.payload["mergeDecisionsJson"])
        decisions = validate_decisions(decision_document, {item["findTableId"] for item in possible})
        write_json(context.paths.helper_json("mergeDecision.json"), decision_document)
        usage = result.token_usage
    value = build_groups(found, decisions)
    write_json(output, value)
    return validate_merge_tables(value, identifiers), usage


def prepare(context: Context, found: dict, possible: list[dict]) -> dict:
    image_dir = context.paths.helper / "merge"
    image_dir.mkdir(parents=True, exist_ok=True)
    by_id = {item["findTableId"]: item for item in found["tables"]}
    pairs = []
    dpi = int(context.params.get("mergeDpi", 180))
    for current in possible:
        previous = by_id.get(current.get("preFindTableId"))
        if previous is None:
            raise ValueError(f"Possible merge has no previous item: {current['findTableId']}")
        images = []
        for role, source in (("previous", previous), ("current", current)):
            target = image_dir / f"{current['findTableId']}-{role}.png"
            rendered = render_page(context.pdf, source["page"], target, dpi, tuple(source["bbox"]))
            images.append(relative(target, context.paths.project))
            source = {**source, "comparisonPixels": {"width": rendered["widthPx"], "height": rendered["heightPx"]}}
            if role == "previous":
                previous = source
            else:
                current = source
        pairs.append({"previous": previous, "current": current, "comparisonImages": images})
    packet = {
        "version": "pdf-table-5/merge-preparation@1.0",
        "decisionRule": "only possible relationships are presented; uncertainty resolves to false",
        "possiblePairs": pairs,
    }
    write_json(context.paths.helper_json("paperMergeTable.json"), packet)
    return packet


def validate_decisions(value: dict, expected: set[str]) -> dict[str, dict]:
    if not isinstance(value, dict) or not isinstance(value.get("decisions"), list):
        raise ValueError("Merge decisions must contain a decisions array")
    result = {}
    for item in value["decisions"]:
        identifier = item.get("findTableId") if isinstance(item, dict) else None
        decision = item.get("mergeWithPrevious") if isinstance(item, dict) else None
        if identifier not in expected or identifier in result or not isinstance(decision, bool):
            raise ValueError(f"Invalid possible-merge decision: {item!r}")
        result[identifier] = item
    if result.keys() != expected:
        raise ValueError(f"Merge decisions omitted IDs: {sorted(expected - result.keys())}")
    return result


def build_groups(found: dict, decisions: dict[str, dict]) -> dict:
    groups = []
    for source in found["tables"]:
        mode = source["mergeWithPrevious"]
        merge = mode == "yes" or (mode == "possible" and decisions[source["findTableId"]]["mergeWithPrevious"])
        member = {**source, "mergeWithPrevious": merge}
        reason = "Finder confirmed continuation" if mode == "yes" else "Finder marked standalone"
        if mode == "possible":
            reason = decisions[source["findTableId"]].get("reason", "Possible relationship resolved")
        if merge and groups:
            groups[-1]["tables"].append(member)
            groups[-1]["reason"] += f"; {reason}"
            groups[-1]["parseTableHint"] = source.get("title") or groups[-1]["parseTableHint"]
        else:
            groups.append({"parseTableHint": source.get("title", ""), "reason": reason, "tables": [member]})
    return {"version": "pdf-table-5/merge-table@1.0", "tables": groups}
