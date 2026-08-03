---
name: pdf-table-codegen
description: Generate and validate reusable, project-local Python extractors for tables in PDF files. Use when an Agent must inspect a PDF visually, freeze a complete table inventory, write PDF-specific extraction code, validate sampled source rows, or integrate deterministic PDF table extraction into a data pipeline without requiring AI at runtime.
---

# PDF Table Codegen

Create code, not a one-off table dump. Keep generic logic in `pdf-table-codegen`
and all document-specific layout decisions in the PDF project's `extractor.py`.

## Workflow

1. Translate the user's request into a project-local `job.yaml`. Read
   [job-format.md](references/job-format.md) for the supported fields and layout.
2. Run `pdf-table-codegen prepare <job.yaml>`. This may render pages and export
   native geometry, but it must not run a table detector. Reuse evidence only
   when the command reports a verified cache hit.
3. Inspect every contact sheet. Open full-resolution pages for all possible
   tables, continuations, uncertain regions, and pages named by a table index.
4. In parallel when possible, have a second Agent independently inspect the
   original page evidence. Do not show it the first inventory or parser
   candidates.
5. Record logical tables, physical segments, page numbers, bboxes, captions,
   continuation groups, and explicit exclusions in a temporary JSON draft.
   Reconcile the independent audit, then run
   `pdf-table-codegen freeze-inventory <job.yaml> <draft.json>`.
6. Run `pdf-table-codegen inspect <job.yaml>`. Review each frozen table's crop
   and neutral word/drawing report; these facts must not change the inventory.
   Use the crop for detailed reference work instead of reopening the same full
   page. Reopen the full page only when surrounding context is still needed.
7. Create a temporary visual-reference draft independently from extractor output.
   Read [audit.md](references/audit.md). When the inventory auditor is available,
   reuse it to transcribe a disjoint subset of frozen tables in parallel while
   the primary Agent handles the remainder; the primary Agent must still confirm
   every merged sample against the crop. Then run
   `pdf-table-codegen freeze-reference <job.yaml> <draft.json>`.
8. Run `pdf-table-codegen scaffold <job.yaml>` to create strategy-neutral
   assertion hints from the frozen reference. Use them only for QA, never to
   construct extracted rows.
9. For each table or layout family, inspect how the PDF represents words,
   reading order, drawings, merged cells, rotation, and continuations. Read
   [extraction-strategies.md](references/extraction-strategies.md), then choose
   the strategy from source evidence rather than from a preferred template.
   Different tables in one PDF may use different strategies.
10. Write the smallest useful project-local `extractor.py`. Treat fixed row bands
   and column edges as one optional strategy, not the default architecture. Use
   posterior table candidates only as disposable geometry hints after the
   inventory is frozen.
11. Expose `can_handle(source)` and `extract_tables(request)`. Return the package's
   `ExtractionResult`; include row provenance and deterministic QA.
12. Run `pdf-table-codegen verify <job.yaml>`. Repair extraction code, not the
   frozen reference, when a source comparison fails.
13. Run the extractor twice and require identical outputs. Integrate by calling
    the same function from any pipeline; do not add a ReIndex dependency to the
    generated extractor.

## Guardrails

- Do not expose Docling, OCR, or PyMuPDF table candidates before visual freeze.
- Do not let candidates add, remove, merge, or split frozen logical tables.
- Keep inventory/reference drafts outside the project directory; only frozen,
  validated evidence belongs in the project.
- Treat table crops, coordinate clusters, and drawing lines as neutral evidence,
  not a required extraction architecture.
- Use Docling or OCR only for a frozen region whose native text layer is unusable.
- Do not require a universal parser, fixed grid, schema DSL, or shared extraction
  helper. Reuse a helper only when the inspected tables genuinely share a layout
  invariant; keep table-specific transforms and fallbacks explicit.
- Detect silent layout drift with table-specific anchors and content assertions,
  not only expected row and column counts.
- Keep source-faithful extraction and normalization explicit in `extractor.py`.
- Reject unknown source hashes by default. Use family compatibility only when
  stable page signatures and regression fixtures exist.
- Never read an older expected CSV before freezing inventory and visual samples.
- Never use the visual reference as extraction input.
- Treat zero-row tables as errors unless explicitly allowed. Handle one-row
  tables without assuming first and last rows are distinct.
- Record the CLI `elapsed_seconds` values plus approximate Agent visual and
  authoring phases. Separate approval/queue latency from active work.

## Runtime API

```python
from pathlib import Path
from pdf_table_codegen import ExtractionRequest
from extractor import extract_tables

result = extract_tables(ExtractionRequest(source=Path("input.pdf")))
```

The returned object is the pipeline boundary. CSV files are a serializer output,
not the only integration mechanism.
