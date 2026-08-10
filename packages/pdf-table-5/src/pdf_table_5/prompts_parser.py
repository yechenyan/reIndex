from __future__ import annotations

from functools import lru_cache

from .agent_context import compact_json
from .agent_schemas import SAMPLE_SCHEMA, SUMMARY_SCHEMA


@lru_cache(maxsize=1)
def fixed_prefix() -> str:
    return f"""PDF-TABLE-5 PARSER PROTOCOL v4

You design or repair one table parser. The orchestrator supplies exact paths, compact word evidence,
images, schemas, and deterministic review feedback. This is runtime extraction, not repository
development or task management. The efficient normal initial path is to use the inline evidence and attached
table crops, reconcile record anchors with geometryHints, then return the structured result directly; the
orchestrator writes and executes it. Repository
discovery, workflow skills, task notes, and scratch candidates normally add no evidence. Shell, PDF tools,
focused screenshots, and runtimePaths.scratchDir remain available when supplied evidence conflicts, a source
must be rechecked, or repair feedback needs diagnosis. Return all authoritative changes as structured output.

RUNTIME LOADER CONTRACT
Use the available canonical loader in generated parsePy:

from pdf_table_5.runtime_geometry import join_word_text, load_segments
segments = load_segments(args.table_json)
for segment in segments:
    words = segment["words"]

Each segment is a plain dictionary: use segment["words"], never segment.words. Its keys are page, bbox,
sourceBbox, geometryPath, images, and words. Runtime words are compact arrays
[x0,y0,x1,y1,text,block,line,word]. Inline evidence losslessly groups repeated y coordinates as
[y0,y1,[[x0,x1,text,block,line,word],...]]; use evidenceEncoding to expand it when reasoning. The loader
resolves raw geometry relative to table.json projectRoot and normalizes object/array records.
runtimePaths.geometryFiles gives absolute paths and
expected wordCount. If a positive count becomes zero, diagnose loading failure; do not classify the table
as an image. For a non-image table, generated code must read runtime geometry or the source PDF and must not
substitute a complete hard-coded output table.

For evidenceMode=boundary, inline evidence and attached crops intentionally contain only the first and last
segments. runtimePaths.geometryFiles still lists every segment, and load_segments() loads them all. Design one
general segment parser from the boundaries and run it across every segment. Inspect a middle geometry/PDF page
with the available tools only when the supplied boundaries conflict or review feedback shows a real problem.

TABLE BOUNDARY CHECK
Before designing samplePy or parsePy, inspect the supplied table crop and use its page-context image when the
target boundary is uncertain. Determine the exact target-table boundary. The crop may contain unrelated
instructions, captions, examples, or adjacent tables; keep them as context but exclude them from extraction.

Require a complete header, first data row, last data row, leftmost column, rightmost column, and visible
table-ending evidence. If grid lines, columns, or data continue beyond any crop edge, treat the crop as
truncated. Use runtimePaths.imageFiles to locate the page-context image. When the boundary still cannot be
confirmed, use runtimePaths.sourcePdf to render a larger crop or the full page inside runtimePaths.scratchDir.
Expand and recheck until the complete table boundary is visible.

The rendered table crop is authoritative for visible cell boundaries, row/column spans, character case, and
legible glyphs. PDF words and coordinates are positioning aids. If extracted words contain OCR corruption,
unexpected symbols, or text that visibly disagrees with the crop, transcribe the crop. Increase render DPI or
inspect a focused crop when needed; never preserve known-bad geometry text or guess unreadable characters.

IMAGE AND NATIVE TABLES
`Abb.`, `Figure`, or `Screenshot` in a title or caption never justifies skipping visible structured rows and columns; skip only when the image contains no target table data.
runtimeClassification.imageTable is orchestrator-owned. When it is false, extract cell text from native PDF
words and coordinates, using the crop to confirm boundaries, merged cells, and ambiguous glyphs.

When runtimeClassification.imageTable is true, the table content is embedded in an image rather than native
PDF words. Read the attached table image directly with your own visual understanding and transcribe the complete
table into parsePy; do not delegate recognition to a generated OCR pipeline. It is permitted for this image-only
case to encode the visually transcribed rows in parsePy. Return samplePy in skip mode with zero totalRows, empty
header/rows, and a non-empty reason stating that the image table was directly read by the Parser LLM. The
orchestrator will perform format-only review and will not run content sampling for this image table.

Before transcribing an image table, confirm that the complete header, all rows, and both outer column edges are
visible. If any part is clipped or unclear, render a wider/full-page or higher-DPI image from
runtimePaths.sourcePdf into runtimePaths.scratchDir and inspect it before returning the parser. Never guess text
that remains unreadable.

Never derive totalRows or sampled rows from a truncated crop. Record the corrected boundary in summary.bboxes.
If the corrected bbox extends beyond the supplied runtime geometry, samplePy and parsePy must read the corrected
region directly from runtimePaths.sourcePdf instead of extracting only the visible load_segments() subset.

For ordered words already assigned to one cell, prefer join_word_text(words). It uses visual-line coordinates
to remove a lower-case line-wrap hyphen, preserves same-line forms such as "Schutz- und", compound prefixes
such as MS-/NS-/ONS-, and a standalone dash cell. It is the shared default for samplePy and parsePy; use a
compareRule when PDF layout still permits equivalent spacing or hyphen forms.

SAMPLE.PY CONTRACT
{compact_json(SAMPLE_SCHEMA)}
Return complete samplePy source implementing: python sample.py --table-json TABLE_JSON. It writes exactly one
JSON object to stdout matching the schema above. With no special comparison rule, simply print the literal
sample JSON. It may use load_segments() to calculate a multi-page sample at runtime. It must not read parse.py,
CSV output, review.json, finalTable.json, or sampleConfirmation.json. parsePy must not read sample.py or
sampleConfirmation.json at runtime.

For content mode, totalRows includes the CSV header. Data rowIndex starts at 1. When there are at most six data
rows, sample every row; otherwise sample rows 1,2,3 and the last three. compareRules is optional. Use
ignore_space_hyphen only when PDF word wrapping makes spaces/hyphens layout-dependent. During initial sampling,
inspect every text column and add this rule immediately for each affected column; do not wait for review failure.
Every rule must have a non-empty columns list and normally uses an empty rowIndexes list to cover that column.
Do not enable it for dates, ranges, identifiers, or numeric columns without clear source wrapping evidence.
For skip mode use zero, empty header/rows, and a non-empty reason. An image table must use skip mode; a native
text/vector target must use content mode. Never synthesize or pad an empty row to satisfy totalRows.

Inspect for cross-row leakage using the source grid, horizontal lines, and reliable row midpoints. Repeated
network nodes, categories, and voltage levels in adjacent rows are legitimate values, not evidence of leakage.

For sqlFriendly output, a source cell that visually spans multiple records belongs to every covered record.
Join all visual lines of that cell and repeat the complete value in each CSV/sample row; do not split a value
such as a date range and its parenthetical qualifier across adjacent records. Repair must not change a correct
repeated sample into visual fragments merely to match faulty CSV output.

Visible cell borders override individual glyph x positions when deciding a merged cell's logical coverage.
Glyph positions inside that merged cell describe typesetting, not column ownership. Never split one merged
value into fragments such as blank, `1`, `(0)`, blank; repeat the complete value in every covered logical column.
Apply the same normalization in Parser, source sample confirmation, Review interpretation, and Repair.

Repeat a value only when the crop visibly proves that one cell spans those rows. Missing or faint grid lines
alone do not prove a merged cell. Use text position and neighboring row boundaries; preserve visibly blank
cells instead of propagating a nearby note through the column.

When a review mismatch differs only by whitespace and the supported hyphen characters, preserve the existing
sample values and add the narrowest ignore_space_hyphen rule to samplePy. Do not rewrite source words or working
parsePy merely to make that layout-only delta exact. Other content differences may require a real samplePy or
parsePy correction.

SUMMARY CONTRACT
{compact_json(SUMMARY_SCHEMA)}
Copy runtimeClassification.imageTable exactly; it is orchestrator-owned. skipped means the candidate is
not an extractable target table, not that extraction was difficult. strategy is empty for self-contained
parsePy or an exact strategy_*.py filename. surroundingText always has before and after strings.

INITIAL RESPONSE
Return complete samplePy and parsePy strings, summary as a nested JSON object, plus strategyFileName and
strategyPy strings. parsePy implements: python parse.py --table-json TABLE_JSON --output ABSOLUTE_CSV. It writes a
UTF-8 rectangular CSV with exactly one header row and never reads sample, summary, review, or finalTable.
Return code only through the structured response fields. Do not edit sample.py, parse.py, summary.json, or shared
strategy files in the runtime workspace; the orchestrator applies the returned artifacts after validation.

REPAIR RESPONSE
Return diagnosis, baseRevision, and changes. Every changes field is present; use null to preserve it.
Change only artifacts required by the diagnosed failure. Repair may change samplePy when its source extraction
or comparison rule is wrong, parsePy when CSV extraction is wrong, or both when necessary. A comparison-rule-only
samplePy change is applied directly. Any raw sample value change is independently confirmed by a new source-only
agent that cannot see generated CSV values, so never derive sample values from review actuals or parser output.
Do not weaken content validation or change imageTable. Start from the precise review delta and use source tools
when needed. A sampleSourceConfirmation in review is authoritative source feedback for later repair attempts.
Review mismatch messages are ordered as `expected sample value != actual CSV value`; the right-hand value is
the current parse.py output. Diagnose and repair the CSV side unless source confirmation changes the sample.
The table crops are attached again on every repair. Before returning, execute the proposed parser in the runtime
workspace and compare its output with every sampled header/row. Do not return a patch that still contains any
reported sampled mismatch; re-inspect the attached crop and correct the extraction logic first.
"""


def parser_prompt(parser_context: dict) -> str:
    return f"""{fixed_prefix()}

DYNAMIC REQUEST
operation: initial-parser
Complete parser context:
{compact_json(parser_context)}
"""


def repair_prompt(
    parser_context: dict,
    artifacts: dict,
    review: dict,
    attempt: int,
    revision: int,
    *,
    include_full_context: bool,
) -> str:
    paths = parser_context["runtimePaths"]
    dynamic = {
        "operation": "repair",
        "review": review,
        "baseRevision": revision,
        "artifactPaths": {
            "samplePy": f'{paths["tableDir"]}/sample.py',
            "summary": f'{paths["tableDir"]}/summary.json',
            "parsePy": f'{paths["tableDir"]}/parse.py',
            "strategyDir": f'{paths["projectRoot"]}/parse/strategy',
        },
        "runtimePaths": paths,
        "runtimeClassification": parser_context["runtimeClassification"],
        "geometryHints": parser_context.get("geometryHints", {}),
        "attempt": attempt,
    }
    if include_full_context:
        dynamic["completeParserContext"] = parser_context
        dynamic["currentArtifacts"] = artifacts
    request = f"DYNAMIC REQUEST\n{compact_json(dynamic)}\n"
    if include_full_context:
        return f"{fixed_prefix()}\n\n{request}"
    return (
        "PDF-TABLE-5 RESUMED SESSION DELTA\n"
        "Continue under the parser protocol and complete context already present in this session.\n"
        f"{request}"
    )
