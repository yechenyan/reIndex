# PDF Parse AI workflow

状态：等待人工审核

## Original request

Implement the complete task described in `packages/pdf-parse/abourt.md` without
modifying that file. Use LiteParse and a newly designed Python architecture; do not
reuse implementation code from `pdf-table-5`. Run the complete workflow against:

`lab-table-parse/bielefelder-netz-2022/2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf`

The accepted scope includes real `gpt-5.6-luna` Codex CLI agent calls at high
reasoning, table extraction and repair, final Markdown/assets/metadata/report, and
successful `execute()` plus `verify()`.

## Constraints

- Keep LiteParse as the only PDF parsing and rendering stack.
- Use the LiteParse 2.13 Python API directly and keep LiteParse OCR disabled.
- Use Pillow only to crop or compose LiteParse-rendered PNG screenshots.
- Use LiteParse's top-left, 72-DPI viewport coordinate system everywhere.
- Runtime owns validated durable writes; agents return structured proposals.
- Prompts are composable fragments and include exact tool usage.
- Do not inspect or modify unrelated project implementation files.
- The requested `$reindex-task-workflow` skill is unavailable in this session;
  this note preserves the required task workflow manually.

## Status

- [x] Read the task specification and repository rules.
- [x] Review current official LiteParse and OpenAI model documentation.
- [x] Confirm the example PDF and Codex CLI are available.
- [x] Implement and test the reusable package.
- [x] Execute and verify the example project.
- [x] Perform documentation consistency review.

## Validation result

- LiteParse 2.13 parsed all 5 pages without OCR or page errors.
- Table discovery produced 5 content-bearing logical table tasks. The classifier
  receives a full-page overview plus a 300-DPI union crop, performs a visual
  coverage audit, and excludes blank/decorative grids. Runtime no longer aligns,
  splits, or merges proposals with vector-line or cell-count heuristics.
- Each table used one persistent Agent session and one structured response for
  both scripts. The prompt requires visual sampling to finish first and forbids
  deriving the parser from `sample.py`; there is no static script-order gate.
- Sampling received page context plus one target-anchor crop with a 48-point
  context margin per page. The Agent was told to sample only, request a bounded
  DPI change when text or dense row counts are uncertain, and keep screenshots
  out of native-text parser execution.
- Review uses normalized character LCS with an 80% threshold for text cells and
  symmetric normalized character LCS comparison for every sampled cell.
- Runtime exposes only `liteparse_page(context, page_number)`. Generated parsers
  directly access native TextItems/words, vector graphics, blocks, rows, cells,
  and AnnotationRect attributes; prompts explicitly distinguish compact inline
  arrays from fresh native Python objects.
- The package test suite passes (29 tests), compileall succeeds, and the wheel
  contains the table/rerender prompts and response schema.
- The final 2026-08-17 clean end-to-end regression passed all 5 tables and
  independent verification returned `ok=true` with no errors or warnings. Output
  contains `table-0001.csv` through `table-0005.csv`; the shared-source
  finalization collision is fixed.
- Clean-run durations were: LiteParse 0.148s, classification 65.085s,
  table-0001 101.847s, table-0002 211.539s, table-0003 65.521s,
  table-0004 83.842s, table-0005 417.352s, and finalization 0.018s
  (945.352s total before the separate verify command).
- Table shapes were 4x4, 4x7, 4x3, 7x4, and 54x20. Repairs were 2, 3, 0, 1,
  and 5. The main table's final repair followed the required conflict order and
  corrected a visual sample row-count error from 55 to 54; parser data already
  contained the sampled final rows.
- Final clean-run usage, including classification, was 1,730,062 input tokens
  (1,013,888 cached), 34,174 output tokens, and 11,629 reasoning-output tokens.
  Resumed-session reporting keeps only the latest cumulative checkpoint instead
  of adding intermediate checkpoints again.
- The task remains active until a human explicitly approves completion.

## Decisions

- Package project: `packages/pdf-parse`.
- Example project: `../lab-table-parse/bielefelder-netz-2022`.
- Agent model: `gpt-5.6-luna`, reasoning effort `medium`; there is no automatic
  Terra escalation.
- Page numbering is 1-based; geometry is top-left viewport points.
- Repeated header/footer image blocks are page chrome and do not require an agent.
- Each project stores a default screenshot DPI; a table Agent may request a
  bounded higher or lower DPI when its current evidence is unreadable.
- The default screenshot resolution is 300 DPI, bounded to 72-600 DPI, a
  12000-pixel side, and 96 million pixels.
- Prompt instructions, not static parser-stack rejection, define the LiteParse
  context root, direct Python API, screenshot role, and prohibited alternatives.
- Failed review may resume the same table session for up to five repairs. Repair
  prompts do not require a minimal edit and never repeat table geometry.
- Failed tables retain the LiteParse fallback with a visible warning.
- Table prompts now inline one revisioned, target-scoped snapshot of native
  LiteParse TextItems/words, vector lines/shapes, and layout blocks. Compact
  schema-plus-array encoding preserves native indices and values while avoiding
  repeated record keys. Runtime does not classify lines, rows, columns, or a
  preferred source block.
- Generated parsers now have one PDF/geometry entry only:
  `liteparse_page(context, page_number)`. The previous normalized word iterator,
  vector-grid bbox rewriting, native/image override, and column-count merge
  rejection have been removed; the visual/classification Agents own those
  judgments.
- The inline snapshot has a SHA-256 revision that a ready proposal reports.
  Runtime records expected, reported, and matched values for audit without
  failing otherwise valid scripts over a copied-string mismatch. The snapshot
  is excluded from parser runtime context and is not resent during repair.
  Screenshot rerenders remain available from 72-600 DPI and send only the new
  images plus the unchanged revision; repair turns reuse session evidence.
- Finalization now retains every parsed table for a shared source block instead
  of overwriting earlier logical tables such as `table-0002` with `table-0003`.
