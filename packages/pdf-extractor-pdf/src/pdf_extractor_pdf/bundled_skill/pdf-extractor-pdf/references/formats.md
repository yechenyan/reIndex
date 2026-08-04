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
      "segments": [
        {
          "id": "segment-01", "page": 2, "bbox": [40, 80, 550, 730],
          "bbox_review": {
            "overlay_sha256": "...",
            "all_visible_table_content_inside": true,
            "reviewed_edges": ["left", "right", "top", "bottom"]
          }
        }
      ]
    }
  ]
}
```

Use one finding per PDF page. A page containing multiple table Segments still
has one `table` finding. A continuation page uses `continuation`. BBoxes are PDF
points in PyMuPDF page coordinates, not image pixels.

Generate the overlay SHA with `audit-inventory`; never invent it. The first audit
normally fails until Finder visually reviews the generated full-page overlays
and copies their hashes into the draft. The second audit freezes that attestation.

## Reference structure draft

Run `scaffold-reference` and fill only the `columns` plus each Segment
`row_count`. Change the spec to
`pdf-extractor-pdf/reference-structure-draft@1.0`, then pass it to
`plan-reference`. Do not invent sample indices: fixed code derives them from
the observed Segment sizes, including both sides of every boundary.

## Reference draft

```json
{
  "spec": "pdf-extractor-pdf/reference-draft@1.0",
  "role": "qa_agent",
  "independent_from_extractor": true,
  "source_evidence_only": true,
  "source_sha256": "...",
  "inventory_sha256": "...",
  "tables": [
    {
      "id": "table-1",
      "columns": ["Name", "Value"],
      "row_count": 3,
      "segment_row_counts": [3],
      "samples": [
        {"row_index": 0, "reasons": ["first_rows"], "values": ["Alpha", "1"]},
        {"row_index": 1, "values": ["Beta", "2"]},
        {"row_index": 2, "values": ["Gamma", "3"]}
      ]
    }
  ]
}
```

All cells are strings copied from source images. The freezer calculates required
sample indices and rejects missing first/last/middle/boundary samples.

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
