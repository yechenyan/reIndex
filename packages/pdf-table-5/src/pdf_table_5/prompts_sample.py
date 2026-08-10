from __future__ import annotations

from .agent_context import compact_json
from .agent_schemas import SAMPLE_SCHEMA


def sample_confirmation_prompt(
    parser_context: dict,
    current_sample: dict | None,
    locations: dict,
    current_error: str | None = None,
) -> str:
    source_context = {
        key: parser_context.get(key)
        for key in (
            "tablePacket", "evidenceEncoding", "evidenceMode", "evidence",
            "geometryHints", "runtimeClassification",
        )
    }
    paths = parser_context.get("runtimePaths", {})
    source_context["sourcePaths"] = {
        key: paths.get(key)
        for key in ("sourcePdf", "tableJson", "geometryFiles", "imageFiles", "scratchDir")
    }
    request = {
        "operation": "confirm-sample-from-source",
        "suspectLocations": locations,
        "currentSample": current_sample,
        "currentSampleError": current_error,
        "sourceContext": source_context,
    }
    return f"""PDF-TABLE-5 SOURCE SAMPLE CONFIRMATION v1

You independently confirm sample values from PDF source evidence. The attached table crops are authoritative
for cell boundaries, visual line grouping, merged cells, and row/column spans. Inline or on-disk PDF geometry
is authoritative for exact characters. Generated CSV, parse.py output, review actual values, and a prior
repair's proposed replacement values are not evidence and are intentionally absent. Do not inspect them.

You retain normal source tools: when supplied evidence is ambiguous, inspect the listed source PDF, geometry,
or make a focused screenshot. Re-evaluate the suspect locations and return a complete samplePy program derived
only from the source. Keep correct current values; correct them only when the PDF source proves they are wrong.
When currentSample is null because its program is invalid, reconstruct the complete sample solely from source
evidence; currentSampleError is diagnostic context, never a source value.
For sqlFriendly output, join a visually spanning cell and repeat its complete value for every covered record.
When visible borders show that one cell spans multiple logical columns, those borders override individual glyph
x positions. A glyph's position inside that merged cell is only typesetting evidence: never bucket fragments
into separate covered columns (for example blank, `1`, `(0)`, blank). Return the complete merged value in every
covered logical column in both the confirmed sample and its samplePy program.
Use column-scoped ignore_space_hyphen rules for source columns whose wrapping makes spaces or hyphens unstable.

Count rows exactly as follows: totalRows includes the header as the first physical row. The header is returned
separately and has no rowIndex. Data rowIndex starts at 1, so the final data rowIndex is totalRows - 1. For
example, one header plus 23 data rows means totalRows=24 and tail rowIndexes 21, 22, 23.

sample.py --table-json TABLE_JSON must print exactly one JSON object matching this schema:
{compact_json(SAMPLE_SCHEMA)}

DYNAMIC SOURCE REQUEST
{compact_json(request)}
"""
