# QA Agent

## Request

Extract all tables into project-local output. Header-neutral matrix: inventory freezes positional column_count; result returns column_count plus rows; row 0 ordinary source row; CSV has no separate header. Do not invent column names. Explicitly account continuation duplicate leading rows.

## Objective

Independently confirm positional column_count, assign exact/text per column, count source rows and repeated leading rows per Segment, decide only unresolved line-wrap candidates, and transcribe planned samples. Row 0 is not implicitly a header. Use exact for numbers/dates/IDs/codes/amounts and text for free text. List every genuinely empty cell in source_blank_indices.

## Allowed inputs

Frozen Inventory, Segment images, neutral geometry, source PDF, and code-detected line-wrap candidates.

## Prohibited inputs

Do not read extractor code, output, result, or extraction logs. Do not invent column names or change code-classified line-wrap decisions.

## Repair scope

Process only these table IDs: table-5. Do not inspect or change other tables. Fixed validation protects unaffected outputs.

## Project boundary

Write only under `/Users/maxiao/Documents/code2/reIndex/testbase/test5-table/sws-netze-solingen-2024`; final tables go in `output/` and all other artifacts in `extractor/`.
