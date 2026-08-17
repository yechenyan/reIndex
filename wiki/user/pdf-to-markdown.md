# Verified PDF-to-Markdown conversion

The independent `packages/pdf-to-markdown` package uses LiteParse for the base document and invokes the
agent-driven `pdf-table-5` workflow only for table pages that need it.

An agent can load the bundled single-file skill directly with only the source PDF:

```text
Follow /absolute/path/reIndex/packages/pdf-to-markdown/skills/SKILL.md
input: /absolute/path/document.pdf
```

The default result is `<pdf-stem>-pdf-to-markdown-run/output.md` next to the source. Its verified run report
is stored at `<pdf-stem>-pdf-to-markdown-run/work/report.json`.
Embedded LiteParse images are stored beside `output.md` under `assets/`, and the Markdown uses relative
`assets/...` references.
LiteParse normally renders table evidence at 300 DPI. For unusually large PDF pages, the converter lowers the document DPI
just enough to keep every rendered page within 25 million pixels and 6000 pixels per side; the effective value
is recorded as `renderDpi` in `artifacts/liteparse.json`.

```bash
uv run pdf-to-markdown document.pdf --output document.md --project document-work
```

Simple tables are not accepted merely because their Markdown is syntactically valid. Codex receives only
the source table crop and returns an independent boundary sample. Deterministic code compares that sample
with the LiteParse matrix. Complex, unreadable, or mismatching tables are parsed by `pdf-table-5` on selected
original page numbers.
Candidate discovery is page-first and also treats dense PDF vector-line grids as table evidence. This catches
continuation pages whose LiteParse complexity counters are zero. Finder may merge consecutive selected pages,
but cannot merge across a missing page number.

The specialist classifies each located table from image coverage and native PDF words inside the table region.
Words in captions or page furniture outside the embedded image do not make it a native-text table. Native tables
use PDF words and coordinates. For an embedded-image table, the Parser LLM directly reads and transcribes the
attached crop, uses skip sampling, and receives format-only review. If the crop is incomplete or unclear, the
Parser LLM must render a wider or higher-DPI source image before returning its parser.

When `pdf-table-5` finds more than one table on a selected page, placement is atomic across the connected page
group. All tables must be accepted before any specialist CSV in that group is inserted. A failed table blocks
the connected replacements and preserves the complete LiteParse fallback. `blockedSpecialistTables` and
`blockedSpecialistPages` explain that decision. `pdf-to-markdown` passes only page numbers; the specialist
Finder independently locates and screenshots the tables.

Successful output has two permitted table statuses:

- `liteparse_verified`: the source crop sample agrees with LiteParse.
- `specialist_verified`: an accepted `pdf-table-5` CSV replaced the LiteParse source span.

Every page replacement is inserted with temporary runtime markers and must appear exactly once; the markers
are removed before output. `report.json` remains `accepted: false` until the atomically written `output.md` has
passed that check, then records the page-to-table audit trail in `specialistPlacements`. If a specialist result
cannot be placed on a requested page or a safe Markdown replacement span cannot be established, conversion
returns nonzero but still writes best-effort Markdown: safe atomic groups are inserted and blocked page groups
retain LiteParse content. The final `accepted: false` report records the failed stage, errors, failed
candidate/specialist IDs, and every placement that was actually applied. Inspect `report.json` and
`artifacts/candidates.json` in the work directory for routing and comparison details.
