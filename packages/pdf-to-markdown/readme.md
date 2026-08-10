# PDF to Markdown

`pdf-to-markdown` converts one PDF to Markdown with a fail-closed table workflow:

1. LiteParse produces Markdown, per-page complexity signals, text geometry, and vector lines in one pass.
   Its document-level DPI is reduced only when necessary so no rendered page exceeds 25 million pixels or
   6000 pixels on either side; ordinary A4 input remains at 150 DPI.
2. Clearly complex or fragmented tables go directly to `pdf-table-5`.
3. Simple tables are rendered and independently sampled by Codex CLI. Code compares the header, total row
   count, first three rows, and last three rows with LiteParse.
4. A failed sample goes to `pdf-table-5`, restricted to the union of required source pages. Candidate
   discovery remains page-first; dense vector grids are table signals even when LiteParse complexity misses
   them, and Finder alone decides whether consecutive selected pages form one logical table.
5. Accepted specialist CSV output replaces every LiteParse table fragment on its source page range as GFM
   Markdown. Placement is page-based and never assumes that LiteParse fragment count equals Finder table count.

If Finder returns multiple tables for one page, replacement is atomic across the connected page group. Only
when every specialist table in that group is accepted does the converter order them by page and visual bbox
and insert them into the replacement region. One rejected table blocks every connected replacement so the
complete LiteParse fallback remains intact. The report records `blockedSpecialistTables` and
`blockedSpecialistPages`. Finder determines the table bboxes and
screenshots; this package supplies only the selected original page numbers. When Finder returns no table for
a requested page, the original LiteParse content is retained and the page is not treated as a failure.
Finder output cannot merge across missing page numbers, preventing a table from silently skipping an
unselected continuation page.

The command returns nonzero when a specialist table is rejected, cannot be placed, or remains unmatched, but
still writes a best-effort `output.md` and final `accepted: false` report. Only atomic groups containing no
failed specialist table are inserted; blocked page groups retain their original LiteParse Markdown. The report records `failedStage`,
`errors`, failed candidate IDs, and failed specialist IDs.

Specialist placement is transactional. Each page group records its source `parseTableIds` and affected
LiteParse `tableIds`; runtime markers prove that every planned group was inserted exactly once and are removed
before writing. Only after the atomic `output.md` write succeeds can `report.json` change to `accepted: true`.
Both successful and best-effort reports expose the applied audit mapping in `specialistPlacements`.

## Usage

```bash
uv run pdf-to-markdown INPUT.pdf --output OUTPUT.md --project WORK_DIR
```

`--project` is optional. By default the work directory is `OUTPUT.md.work`. Reusing a work directory lets
the specialist workflow resume its verified intermediates. If table grouping changes the selected page set,
the generated `specialist/` workspace is rebuilt automatically so stale partial-page results are not reused.

LiteParse embedded images are written to an `assets/` directory next to the requested Markdown file. Image
references in the Markdown use relative paths such as `assets/img_p3_1.jpg`.

Agents can load the bundled single-file skill directly with only an input path:

```text
Follow /absolute/path/reIndex/packages/pdf-to-markdown/skills/SKILL.md
input: /absolute/path/document.pdf
```

The skill writes `output.md` and `work/report.json` under
`<pdf-stem>-pdf-to-markdown-run/` next to the input PDF unless the user requests another destination.

Model settings apply to both the source-sampling Agent and the specialist workflow:

```bash
uv run pdf-to-markdown INPUT.pdf \
  --output OUTPUT.md \
  --model gpt-5.6-terra \
  --reasoning-effort medium
```

The project retains auditable artifacts:

```text
WORK_DIR/
├── job.json
├── artifacts/
│   ├── liteparse.json
│   ├── candidates.json
│   ├── samples.json
│   ├── screenshots/
│   └── agents/
├── specialist/
└── report.json
```

`candidates.json` records every candidate's source pages, bbox, Markdown spans, routing reasons, sample
comparison, specialist mapping, and final verification status.
`liteparse.json` records the effective adaptive DPI as `renderDpi`.

## Python API

```python
from pdf_to_markdown import convert

report = convert("input.pdf", "output.md", project="conversion-work")
```
