# Draft formats

## Inventory draft

```json
{
  "spec": "pdf-extractor-pdf/inventory-draft@1.0",
  "role": "finder_agent",
  "reviewed_all_pages": true,
  "source_sha256": "...",
  "page_findings": [
    {"page": 1, "label": "no_table", "notes": "cover"},
    {"page": 2, "label": "table", "notes": "Table 1"}
  ],
  "tables": [
    {
      "id": "table-1",
      "title": "Table 1",
      "column_count": 2,
      "segments": [
        {"id": "segment-01", "page": 2, "bbox": [40, 80, 550, 730]}
      ]
    }
  ]
}
```

Use one finding per PDF page. A page containing multiple table Segments still
has one `table` finding. A continuation page uses `continuation`. BBoxes are PDF
points in PyMuPDF page coordinates, not image pixels.

The first audit generates `inventory-review.json` and binds every overlay hash.
Finder fixes blocking bboxes, then edits only the visibility boolean and four
reviewed edges in that file. The next audit freezes the attestation.

## Reference structure draft

Run `scaffold-reference` and confirm the frozen positional `column_count`, fill
one `comparison_modes` entry per column, and fill each Segment's
`source_row_count` and `repeated_leading_rows`. Row 0 is an ordinary source row,
not a special header. Code preclassifies obvious line-wrap candidates; QA fills
only unresolved `decision` values. Change the spec to
`pdf-extractor-pdf/reference-structure-draft@2.0`, then pass it to
`plan-reference`. Do not invent sample indices: fixed code derives them from
the observed Segment sizes, including both sides of every boundary.

## Reference draft

```json
{
  "spec": "pdf-extractor-pdf/reference-draft@2.0",
  "role": "qa_agent",
  "independent_from_extractor": true,
  "source_evidence_only": true,
  "source_sha256": "...",
  "inventory_sha256": "...",
  "tables": [
    {
      "id": "table-1",
      "column_count": 2,
      "comparison_modes": ["text", "exact"],
      "row_count": 3,
      "segment_row_counts": [3],
      "segment_source_row_counts": [3],
      "segment_repeated_leading_rows": [0],
      "line_wrap_decisions": [{
        "id": "wrap-...", "line_end": "Zusammenfas-",
        "next_line_start": "sen", "decision": "remove", "occurrences": []
      }],
      "samples": [
        {"row_index": 0, "reasons": ["first_rows"], "values": ["Alpha", "1"], "source_blank_indices": []},
        {"row_index": 1, "values": ["Beta", "2"]},
        {"row_index": 2, "values": ["Gamma", "3"]}
      ]
    }
  ]
}
```

All cells are strings copied from source images. Use `text` only for free text;
use `exact` for numbers, dates, IDs, codes, and amounts. Every empty value must
list its zero-based column index in `source_blank_indices`. `column_count` must
match Inventory, and every sample width must match it. A continuation Segment's
repeated leading rows are counted but excluded from retained row counts; the
first Segment must declare zero repeated rows. The freezer rejects undeclared
blanks and missing first-three/last-two/middle/boundary samples. No column names exist in
the extraction truth layer.

## Merge-decision draft

```json
{
  "spec": "pdf-extractor-pdf/merge-decisions-draft@1.0",
  "role": "main_agent",
  "inventory_sha256": "...",
  "decisions": [{
    "left": "table-3",
    "right": "table-4",
    "decision": "keep_separate",
    "reason": "Distinct source captions and datasets.",
    "evidence_pages": [13, 14]
  }]
}
```

Only visually confirmed `keep_separate` decisions belong here. The freezer adds
the cited Segment image/geometry hashes. A confirmed merge is not a decision-file
case: reopen Inventory and repair the logical table/Segment ownership.

## Agent metric

```json
{
  "role": "finder_agent",
  "agent_id": "agent-finder-1",
  "model": "gpt-5.6-terra",
  "started_at": "2026-08-04T00:00:00Z",
  "ended_at": "2026-08-04T00:10:00Z",
  "wall_seconds": 600,
  "active_seconds": 520,
  "conversation_turns": 1,
  "repair_rounds": 0,
  "token_usage": null,
  "blockers": [],
  "notes": "Host did not expose exact token telemetry."
}
```

Production runs record four separate metrics, one each for `main_agent`,
`finder_agent`, `extraction_agent`, and `qa_agent`; extraction and QA timestamps
must overlap.
