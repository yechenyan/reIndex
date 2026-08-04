# Extraction Agent

## Request

Extract every visible source table as header-neutral positional CSV matrices, preserving segment order, text, numeric values, and row provenance.

## Objective

Implement project main.py for the frozen header-neutral matrix Inventory with row provenance and merge policy. Preserve row 0; remove only explicitly repeated leading rows on continuation Segments. Fix wrong row/column alignment in table-specific code. Generated project code has no artificial 200-line limit.

## Allowed inputs

Frozen Inventory, Segment images, neutral geometry, source PDF.

## Prohibited inputs

Do not read QA reference drafts or frozen reference; do not invent column names or emit a separate header array.

## Repair scope

Process only these table IDs: table-6. Do not inspect or change other tables. Fixed validation protects unaffected outputs.

## Project boundary

Write only under `/Users/maxiao/Documents/code2/reIndex/testbase/test5-table/bielefelder-netz-2022`; final tables go in `output/` and all other artifacts in `extractor/`.
