from __future__ import annotations

from .agent_context import compact_json


def finder_prompt(finder_context: dict) -> str:
    return f"""You are the Finder for a PDF table extraction workflow. The complete task context is
embedded below, and the rendered page images are attached in the same order as the non-skipped pages.

Suggested process:
1. Visually inspect every attached page.
2. Record actual data tables, including borderless tables and page continuations. Exclude prose,
   charts, contents pages, abbreviation lists, and diagrams without tabular data.
   Treat one visually continuous grid as one table. Never create another table entry for only a subset
   of that grid. A bbox may contain reasonable surrounding context; the Parser will refine its boundary.
3. Give each segment an approximate visual-page bbox with the generous requested margin. Precision is
   not the goal: keep the entire table, caption, and safe surrounding space inside the bbox.
4. Mark continuity as yes only when certain, possible when adjacent segments may continue, otherwise no.
5. Return the completed JSON document in the structured field findTableJson.

All ordinary-path evidence is already present, so direct visual reasoning and a structured response are
the expected workflow; repository discovery, local PDF inspection, and output validation are unnecessary.

findTableJson shape:
{{"version":"pdf-table-5/find-table@1.0","tables":[{{"findTableId":"find_0001",
"preFindTableId":null,"page":1,"bbox":[x0,y0,x1,y1],"title":"",
"mergeWithPrevious":"yes|possible|no","recommendedDpi":216,"reason":"visual evidence"}}]}}

Complete finder context:
{compact_json(finder_context)}
"""


def finder_repair_prompt(finder_context: dict, invalid_json: str, error: str) -> str:
    return f"""Produce a corrected findTableJson from the complete inline context below. The previous
structured value failed deterministic validation with: {error}

Suggested process: correct only the structural or coordinate problem, retain visually supported table
decisions, and return the full replacement JSON document.

Previous value:
{invalid_json}

Complete finder context:
{compact_json(finder_context)}
"""


def merge_prompt(merge_context: dict) -> str:
    return f"""You are resolving only Finder relationships marked possible. Relationships marked yes
are already merged deterministically; relationships marked no are already separated. The complete
possible-pair context is embedded below and its comparison images are attached in listed order.

Suggested process:
1. Compare the two segments in each possible pair using headers, columns, titles, row flow, and footnotes.
2. Resolve uncertainty to false.
3. Return one decision for every possible findTableId in mergeDecisionsJson.

Normal completion uses the inline records and attached images directly; no repository inspection or local
validation is needed.

mergeDecisionsJson shape:
{{"version":"pdf-table-5/merge-decisions@1.0","decisions":[{{"findTableId":"find_0002",
"mergeWithPrevious":false,"reason":"visual evidence"}}]}}

Complete merge context:
{compact_json(merge_context)}
"""
