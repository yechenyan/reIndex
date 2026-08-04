# Main Agent

## Request

Read-only extraction of every visible table from the 16-page Mainzer Netze 2024 PDF into positional CSV/JSON outputs. Preserve all visible rows, columns, blank cells, and segment provenance; no PDF modification. Use frozen inventory and independent source-only QA.

## Objective

Own requirements, positional-column ambiguity, merge decisions, and final review. Tables are header-neutral matrices: row 0 is an ordinary source row. Treat format_only differences as non-blocking; route real row/column/content errors only.

## Allowed inputs

All project evidence and reports.

## Prohibited inputs

Do not author QA source values or invent column names.

## Repair scope

Process only these table IDs: table-appendix-measures. Do not inspect or change other tables. Fixed validation protects unaffected outputs.

## Project boundary

Write only under `/Users/maxiao/Documents/code2/reIndex/testbase/test5-table/mainzer-netze-2024`; final tables go in `output/` and all other artifacts in `extractor/`.
