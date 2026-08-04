# Main Agent

## Request

Extract all tables into project-local output. Header-neutral matrix: inventory freezes positional column_count; result returns column_count plus rows; row 0 ordinary source row; CSV has no separate header. Do not invent column names. Explicitly account continuation duplicate leading rows.

## Objective

Own requirements, positional-column ambiguity, merge decisions, and final review. Tables are header-neutral matrices: row 0 is an ordinary source row. Treat format_only differences as non-blocking; route real row/column/content errors only.

## Allowed inputs

All project evidence and reports.

## Prohibited inputs

Do not author QA source values or invent column names.

## Repair scope

Process only these table IDs: table-5. Do not inspect or change other tables. Fixed validation protects unaffected outputs.

## Project boundary

Write only under `/Users/maxiao/Documents/code2/reIndex/testbase/test5-table/sws-netze-solingen-2024`; final tables go in `output/` and all other artifacts in `extractor/`.
