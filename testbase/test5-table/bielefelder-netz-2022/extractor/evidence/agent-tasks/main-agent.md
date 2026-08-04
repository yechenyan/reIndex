# Main Agent

## Request

Extract every visible source table as header-neutral positional CSV matrices, preserving segment order, text, numeric values, and row provenance.

## Objective

Own requirements, positional-column ambiguity, merge decisions, and final review. Tables are header-neutral matrices: row 0 is an ordinary source row. Treat format_only differences as non-blocking; route real row/column/content errors only.

## Allowed inputs

All project evidence and reports.

## Prohibited inputs

Do not author QA source values or invent column names.

## Repair scope

Process only these table IDs: table-6. Do not inspect or change other tables. Fixed validation protects unaffected outputs.

## Project boundary

Write only under `/Users/maxiao/Documents/code2/reIndex/testbase/test5-table/bielefelder-netz-2022`; final tables go in `output/` and all other artifacts in `extractor/`.
