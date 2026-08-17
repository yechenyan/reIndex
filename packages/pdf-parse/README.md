# pdf-parse

`pdf-parse` converts a PDF into ordered Markdown, extracted images, verified CSV
tables, metadata, and an execution report. It uses the LiteParse 2.13 Python API
for parsing, geometry, layout blocks, embedded images, and screenshots. LiteParse
OCR is always disabled; image-only content is read directly by a visual Agent.

## Commands

```bash
uv run pdf-parse init INPUT.pdf --project PROJECT_DIR
uv run pdf-parse run PROJECT_DIR
uv run pdf-parse verify PROJECT_DIR
```

The generated `PROJECT_DIR/parse/main.py` also exposes `execute()` and `verify()`.
`run` is resumable: `states.json` is the authoritative snapshot and
`steps.jsonl` is the append-only event history. A changed source PDF hash stops
the workflow instead of silently reusing artifacts.

## Workflow

1. LiteParse parses the document once with layout blocks, word boxes,
   complexity signals, vector graphics, content bounds, and embedded images.
2. Repeated top/bottom page chrome is ignored. `needs_ocr` caused only by such
   chrome never routes a full page to an Agent.
3. A visual classifier corrects only uncertain blocks and identifies logical
   table regions. Runtime validates IDs and page bounds but does not rewrite the
   Agent's regions with vector-line clustering or cell-count heuristics.
4. Each logical table gets one persistent Codex session and one response that
   contains both scripts. The prompt requires the Agent to finish a fixed visual
   `sample.py` first, then independently inspect one inline snapshot of scoped
   native LiteParse geometry and create the general `parse.py`; the parser may
   not read or hard-code the sample. Neither script classifies a row as header
   or body: both use the same ordered physical-row matrix.
5. Runtime independently syntax-checks and runs both scripts, collects every
   discoverable error in one review, and reports LCS failures by physical row
   and column. Every cell must reach 80% symmetric normalized character LCS.
   Visual samples do not define column-specific comparison rules.
6. Failed review resumes the same Agent session for up to five repairs.
   Repair turns never repeat geometry or screenshot bytes. Code errors receive
   only errors and the last generated table; LCS conflicts instruct the same
   session to re-read its existing whole-table screenshot and fix a bad sample
   before changing parser logic. A failed table does not stop other tables.
7. Runtime assembles `output.md` from the ordered document block graph and
   writes CSV assets, metadata, and reports. Failed tables retain the LiteParse
   fallback with a visible warning.

## Screenshot resolution

Every project stores its global default DPI in `parse/helper/params.json`:

```json
{
  "screenshots": {
    "defaultDpi": 300,
    "minDpi": 72,
    "maxDpi": 600,
    "maxImageSide": 12000,
    "maxImagePixels": 96000000
  }
}
```

An Agent can request a higher or lower DPI when evidence is unreadable. Runtime
clamps it to the project limits, re-renders full-page/crop evidence, and resumes
the same session with the replacement images but without repeating geometry.
The Agent always receives a page overview and one
bounded whole-table crop per involved page; evidence is not split into rows.
Once review starts, images are never attached again; the persistent session
retains the original or rerendered screenshot for visual conflict review.

Generated scripts use fixed Runtime entries for argparse, context loading, JSON
output, and one LiteParse 2.13 loader: `liteparse_page(context, page_number)`.
The initial prompt embeds the latest target-scoped `page.text_items`,
`page.vector_graphics.lines/shapes`, and `page.blocks` hierarchy in a lossless
compact record encoding with a SHA-256 revision. Runtime performs only geometric
intersection scoping over a fixed 48-point context margin; the classifier bbox
remains a target anchor rather than an asserted table edge. The Agent decides
whether lines, blocks, cells, or words best explain the table. Generated parsers
receive fresh native LiteParse objects and directly use
`word.x/y/width/height`, never `word.bbox`. Agents default to
medium reasoning, and resumed-session token usage records the latest cumulative
checkpoint instead of adding earlier checkpoints again.

## Generated project

```text
PROJECT_DIR/
├── parse/
│   ├── main.py
│   ├── helper/       # job, params, state, events, blocks, native geometry, screenshots
│   ├── blocks/       # per-table evidence, sample.py, parse.py, review, summary
│   ├── report/       # summary and verify reports
│   └── scratch/
└── output/
    ├── output.md
    ├── metadata.json
    └── assets/       # table CSVs and extracted source images
```

Coordinates are 1-based by page and use LiteParse's top-left 72-DPI viewport
points throughout. Physical table rows are 1-based: the top visible table row is
always row 1, whatever its semantic role. Parser JSON is `{"rows": [...]}`;
CSV and generated Markdown preserve all rows without a semantic header.
