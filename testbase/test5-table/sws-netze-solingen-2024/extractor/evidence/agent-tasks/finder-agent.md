# Finder Agent

## Request

Extract all tables into project-local output. Header-neutral matrix: inventory freezes positional column_count; result returns column_count plus rows; row 0 ordinary source row; CSV has no separate header. Do not invent column names. Explicitly account continuation duplicate leading rows.

## Objective

Inspect every PDF page and draft the complete logical-table Inventory, including each table's positional column_count.

## Allowed inputs

Finder packet, rolling contact sheets, pre-rendered candidate pages, and targeted uncertain pages.

## Prohibited inputs

Do not read extractor code, output, or prior answers. Do not assume row 0 is a header. Start with finder-packet.json; do not rerender pages already supplied.

## Repair scope

Process only these table IDs: table-5. Do not inspect or change other tables. Fixed validation protects unaffected outputs.

## Project boundary

Write only under `/Users/maxiao/Documents/code2/reIndex/testbase/test5-table/sws-netze-solingen-2024`; final tables go in `output/` and all other artifacts in `extractor/`.
