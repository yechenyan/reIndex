# QA Agent

## Request

Read-only extraction of every visible table from the 16-page Mainzer Netze 2024 PDF into positional CSV/JSON outputs. Preserve all visible rows, columns, blank cells, and segment provenance; no PDF modification. Use frozen inventory and independent source-only QA.

## Objective

Independently confirm positional column_count, assign exact/text per column, count source rows and repeated leading rows per Segment, decide only unresolved line-wrap candidates, and transcribe planned samples. Row 0 is not implicitly a header. Use exact for numbers/dates/IDs/codes/amounts and text for free text. List every genuinely empty cell in source_blank_indices.

## Allowed inputs

Frozen Inventory, Segment images, neutral geometry, source PDF, and code-detected line-wrap candidates.

## Prohibited inputs

Do not read extractor code, output, result, or extraction logs. Do not invent column names or change code-classified line-wrap decisions.

## Repair scope

Process only these table IDs: table-appendix-measures. Do not inspect or change other tables. Fixed validation protects unaffected outputs.

## Project boundary

Write only under `/Users/maxiao/Documents/code2/reIndex/testbase/test5-table/mainzer-netze-2024`; final tables go in `output/` and all other artifacts in `extractor/`.
