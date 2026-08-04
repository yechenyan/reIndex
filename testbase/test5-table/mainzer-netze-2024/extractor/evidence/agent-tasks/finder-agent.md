# Finder Agent

## Request

Read-only extraction of every visible table from the 16-page Mainzer Netze 2024 PDF into positional CSV/JSON outputs. Preserve all visible rows, columns, blank cells, and segment provenance; no PDF modification. Use frozen inventory and independent source-only QA.

## Objective

In one dispatch, inspect every page, draft the complete Inventory with positional column_count, run audit-inventory, apply required BBox repairs, attest every reviewed edge, and rerun the audit until it passes. Return only a freeze-ready draft; do not stop after writing the first draft.

## Allowed inputs

Finder packet, rolling contact sheets, pre-rendered candidate pages, targeted uncertain pages, Inventory audit overlays, and inventory-review.json.

## Prohibited inputs

Do not read extractor code, output, or prior answers. Do not assume row 0 is a header or rerender pages already supplied.

## Repair scope

Process only these table IDs: table-appendix-measures. Do not inspect or change other tables. Fixed validation protects unaffected outputs.

## Project boundary

Write only under `/Users/maxiao/Documents/code2/reIndex/testbase/test5-table/mainzer-netze-2024`; final tables go in `output/` and all other artifacts in `extractor/`.
