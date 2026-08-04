# PDF extractor rotated-page audit

Status: active; awaiting human approval.

## User request

Fix Inventory Audit for rotated PDF pages with the simple display-coordinate
mapping, then delete the Bielefelder fixture's generated `output/` and
`extractor/` directories and rerun it with a new GPT-5.6 Terra Agent.

## Scope

- Convert text rectangles and drawing endpoints with `page.rotation_matrix`
  before comparing them with display-coordinate Segment bboxes.
- Cover 0, 90, 180, and 270 degree page rotations with a regression test.
- Preserve hard gates, Inventory formats, Finder behavior, and generated
  project isolation.
- Run a clean Bielefelder benchmark and retain metrics and review evidence.

## Validation

- `test_inventory_audit_uses_display_coordinates_on_rotated_pages` covers
  0, 90, 180, and 270 degrees, preserves genuine clipped-word detection, and
  checks transformed drawing-line advisories.
- Package tests: 36 passed; source and wheel builds succeeded.
- The prior Bielefelder draft changed from a permanent rotated-page failure to
  `passed=true` with zero blocking signals before the clean rerun.
- Clean GPT-5.6 Terra rerun completed all hard gates: 6 tables, 6 Segments, 80
  rows, final review 005 with zero issues and zero merge candidates.
- All six CSV files exactly match `result.json`; `check` and `verify-cache`
  passed independently after finalization.
- Telemetry: 10 child conversations, 7 follow-ups, 19 main orchestration steps;
  host token telemetry remained unavailable.
