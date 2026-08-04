# Finder Agent

## Request

Extract all tables from the source PDF into CSV files with conservative source-faithful values and row-level provenance.

## Objective

Inspect every PDF page and draft the complete logical-table Inventory.

## Allowed inputs

Source PDF, low pages, contact sheets, targeted high pages.

## Prohibited inputs

Do not read extractor code, output, or prior answers.

## Repair scope

Process only these table IDs: table-5. Do not inspect or change other tables. Fixed validation protects unaffected outputs.

## Project boundary

Write only under `/Users/maxiao/Documents/code2/reIndex/testbase/test5-table/sws-netze-solingen-2024`; final tables go in `output/` and all other artifacts in `extractor/`.
