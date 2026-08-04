# Extraction Agent

## Request

Extract all tables into project-local output. Header-neutral matrix: inventory freezes positional column_count; result returns column_count plus rows; row 0 ordinary source row; CSV has no separate header. Do not invent column names. Explicitly account continuation duplicate leading rows.

## Objective

Implement project main.py for the frozen header-neutral matrix Inventory with row provenance and merge policy. Preserve row 0; remove only explicitly repeated leading rows on continuation Segments. Fix wrong row/column alignment in table-specific code. Generated project code has no artificial 200-line limit.

## Allowed inputs

Frozen Inventory, Segment images, neutral geometry, source PDF.

## Prohibited inputs

Do not read QA reference drafts or frozen reference; do not invent column names or emit a separate header array.

## Repair scope

Process only these table IDs: table-5. Do not inspect or change other tables. Fixed validation protects unaffected outputs.

## Project boundary

Write only under `/Users/maxiao/Documents/code2/reIndex/testbase/test5-table/sws-netze-solingen-2024`; final tables go in `output/` and all other artifacts in `extractor/`.
