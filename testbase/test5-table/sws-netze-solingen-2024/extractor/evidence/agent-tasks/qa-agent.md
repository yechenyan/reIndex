# QA Agent

## Request

Extract all tables from the source PDF into CSV files with conservative source-faithful values and row-level provenance.

## Objective

Independently fill reference structure, row counts, and planned source samples.

## Allowed inputs

Frozen Inventory, Segment images, neutral geometry, source PDF.

## Prohibited inputs

Do not read extractor code, output, result, or extraction logs.

## Repair scope

Process only these table IDs: table-5. Do not inspect or change other tables. Fixed validation protects unaffected outputs.

## Project boundary

Write only under `/Users/maxiao/Documents/code2/reIndex/testbase/test5-table/sws-netze-solingen-2024`; final tables go in `output/` and all other artifacts in `extractor/`.
