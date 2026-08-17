# Verified PDF parsing with `pdf-parse`

Use `pdf-parse` when a PDF needs ordered Markdown plus table CSVs that are
visually sampled and checked. It is a local, resumable workflow built on the
LiteParse 2.13 Python API and Codex visual Agents.

## Run a project

```bash
uv run pdf-parse init /absolute/source.pdf --project /absolute/project
uv run pdf-parse run /absolute/project
uv run pdf-parse verify /absolute/project
```

`run` can be called again after interruption. Completed LiteParse,
classification, and terminal table results are reused while the source SHA-256
is unchanged.

## Parsing behavior

- LiteParse OCR is disabled. Native PDF text and word geometry remain the
  primary source; image tables are transcribed directly by the visual Agent.
- Repeated page headers, footers, logos, and page numbers are treated as page
  chrome. A page-level `needs_ocr` flag caused by that chrome does not trigger
  full-page Agent processing.
- A table uses one persistent Agent session and one response containing both
  scripts. The prompt requires the Agent to visually finish the fixed sample
  before independently writing the general parser. Evidence is one bounded
  whole-table crop per involved page, never per-row images.
- Sampling and parsing both use a single ordered physical-row matrix. The top
  visible row is row 1; no row is classified as header or body. CSV and generated
  HTML table output preserve that order without a semantic header section.
- Runtime uses symmetric normalized character LCS at an 80% threshold and
  reports failures by physical row and column. Samples do not carry
  column-specific comparison rules.
- The project default DPI and allowed range live in `parse/helper/params.json`.
  An Agent may request a different DPI and is resumed with new screenshots.
- A table may pass, fail, be wrong, or be skipped. Failures are reported but do
  not stop later tables. Final Markdown keeps LiteParse content as a warning
  fallback when specialist extraction is not trustworthy.
- Generated scripts use fixed argparse, context, JSON-output, and LiteParse 2.13
  entry functions. Native words are exposed as normalized text plus
  `[x, y, width, height]` records; generated parsers do not inspect LiteParse
  bbox object types. Numbers and adjacent currency/unit fragments stay in the
  same geometrically selected cell. A failed review resumes the same
  medium-reasoning Agent for at most five repairs. Repair turns never repeat
  geometry. Code errors do not receive screenshots; LCS conflicts receive the
  whole-table image and must visually correct the sample first, then review
  again, before parser logic may be changed.

## Outputs

- `output/output.md`: content assembled in document-block order with source
  page/bbox comments and CSV links.
- `output/assets/`: table CSV files and extracted images.
- `output/metadata.json`: ordered block/page/bbox/artifact relationships.
- `parse/report/summary.json`: table status, repairs, tokens, and problems.
- `parse/report/verify.json`: deterministic final verification result.

See the package [README](../../packages/pdf-parse/README.md) for the runtime
layout and detailed workflow.
