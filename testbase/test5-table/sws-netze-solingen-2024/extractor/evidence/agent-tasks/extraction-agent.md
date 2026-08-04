# Extraction Agent

## Request

Extract all tables from the source PDF into CSV files with conservative source-faithful values and row-level provenance.

## Objective

Implement project main.py for the frozen Inventory with row provenance and merge policy.

## Allowed inputs

Frozen Inventory, Segment images, neutral geometry, source PDF.

## Prohibited inputs

Do not read QA reference drafts or frozen reference.

## Repair scope

Process only these table IDs: table-5. Do not inspect or change other tables. Fixed validation protects unaffected outputs.

## Project boundary

Write only under `/Users/maxiao/Documents/code2/reIndex/testbase/test5-table/sws-netze-solingen-2024`; final tables go in `output/` and all other artifacts in `extractor/`.
