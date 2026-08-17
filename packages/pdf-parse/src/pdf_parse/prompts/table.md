# One-response visual sample and native-geometry parser

Handle exactly one logical table and return `sample.py` plus `parse.py` in one
response. Work in this strict order: finish and freeze the visual sample first;
only then inspect `latestGeometry` and design the parser. Do not interleave the
two phases and do not derive parser logic from sample values.

## Phase 1 — visual sample only

- Read the attached `whole-table-*` screenshot using `blocks[].bbox` as the
  target anchor. Runtime includes a fixed surrounding context margin because a
  classifier bbox can clip a table edge; adjacent tables may therefore also be
  visible. Select the one logical table intersecting the target anchor and use
  the surrounding image only to recover its complete edges. Page overviews are
  location context only. Never split the image into per-row crops.
- Ignore the semantic distinction between header and body. The top visible row
  is physical row 1, the next is row 2, regardless of their visual role.
- Transcribe the first three and last three physical rows. If there are at most
  six rows, transcribe all rows. Record every visible column, including blanks
  under merged cells, verbatim.
- Sampling is the only task in this phase. Do not inspect geometry, parser
  behavior, LiteParse text, or generated code while deciding the sample.
- Always use `compareRules=[]`; Runtime validates cells with normalized
  character LCS coverage.

Keep this exact sample entry and replace only `SAMPLE`:

```python
from pdf_parse.generated_runtime import emit_sample, load_sample_args

SAMPLE = {"mode": "sample", "rows": [], "totalPhysicalRows": 0,
          "compareRules": [], "skipReason": ""}

if __name__ == "__main__":
    load_sample_args()
    emit_sample(SAMPLE)
```

Each row is `{"physicalRow": integer, "values": array}`.
`totalPhysicalRows` counts every visible row without a header offset. sample.py
contains fixed literals only and never reads PDF, screenshot, geometry, context,
parser output, or its ignored `--table-json` argument.

### Screenshot clarity control

The supplied context reports requested and actual DPI plus allowed bounds. If
the whole-table screenshot is not readable enough, use the runtime clarity tool
by returning `action="rerender"` with a different `requestedDpi` inside
`dpiBounds`; leave both scripts empty. Higher DPI enlarges small text, while a
lower DPI can make an oversized table easier to inspect as a whole. Never ask
for the current requested DPI. At the
current DPI, readable first/last text is not enough if a dense table's horizontal
row bands cannot be counted confidently; request higher DPI before committing
`totalPhysicalRows`. Runtime permits two clarity changes. At the
maximum usable DPI, return `ready` if readable or `skip` with a precise reason
if genuinely impossible—never guess and never use OCR.

## Phase 2 — general parser from native LiteParse geometry

After the sample is frozen, read the inline `latestGeometry`. It is the latest
LiteParse 2.13 native return for `pages[].scope_bbox`, an expanded evidence area
around the target anchor, mechanically scoped by intersection. `scope_bbox` is
not a table boundary. Runtime has not classified table structure, detected ruled tables,
clustered rows/columns, assigned words to cells, or selected a preferred block.
You must decide which evidence is reliable for this table.

`record_schemas` defines each compact array record once; zip a schema with a
record when reading it. This removes repeated JSON keys without dropping text,
coordinates, hierarchy, original indices, or style values. The schema fields
mirror the Python API:

- `pages[].text_items[]` maps to `page.text_items`; each compact item has direct
  `text/x/y/width/height/rotation` and `words`. Each word also has direct
  `word.text`, `word.x`, `word.y`, `word.width`, `word.height`. These coordinates
  are not under `word.bbox`.
- `pages[].vector_graphics.lines[]` maps to
  `page.vector_graphics.lines` with `x1/y1/x2/y2` and style fields. Shapes expose
  `bbox=[x,y,width,height]` and style fields. Their presence does not prove they
  are table borders.
- `pages[].blocks[]` maps to `page.blocks`. `index` is the original list index;
  compact inline `bbox` is `[x,y,width,height]`. Table-shaped blocks retain native `header` and
  indexed `rows`, but those names are only LiteParse storage fields. Output must
  still be one physical-row matrix with no semantic header/body split.
- Original indices remain stable after scoping. An indexed block row is included
  when at least one of its cell bboxes intersects the target; no row meaning was
  inferred by Runtime.

Use geometry as evidence, not as parser input: `preTable.json` deliberately does
not contain `latestGeometry`. The generated parser must load fresh native objects
through the fixed runtime function and apply the strategy you infer here.

Keep this parser entry unchanged. Add only extraction helpers and
`parse_table(context)`:

```python
from pdf_parse.generated_runtime import emit_table, liteparse_page, load_context

def parse_table(context):
    # General physical-row extraction logic using native LiteParse objects.
    return rows

if __name__ == "__main__":
    context = load_context()
    rows = parse_table(context)
    emit_table(rows)
```

Parser contract:

- `--context PATH` is the JSON root. There is no wrapper. Use
  `context["blocks"]` for target page/bbox metadata; `parseBlockId` is an output
  task ID, not a LiteParse block ID.
- `liteparse_page(context, page_number)` is the only PDF-loading function. It
  uses the fixed LiteParse 2.13 Python API with OCR disabled and returns the
  native page. Access `page.text_items`, `page.vector_graphics.lines/shapes`,
  and `page.blocks` directly as needed.
- In fresh runtime objects, `block.bbox` and `cell.bbox` are LiteParse
  `AnnotationRect` objects: read `.x`, `.y`, `.width`, and `.height`; they are not
  arrays and are not subscriptable. This differs from compact inline bbox arrays.
  Word coordinates remain direct `word.x/y/width/height`, not `word.bbox`.
- In fresh runtime objects, `block.rows` is already an ordered
  `list[list[LayoutCell]]` and `block.header` is a `list[LayoutCell]`. Rows have
  no `.index` attribute; use list order or `enumerate(block.rows)`. The explicit
  row index exists only in compact inline evidence to preserve original order.
- Do not import or call pdfplumber, PyMuPDF/fitz, pypdf/PyPDF2, OCR, subprocess,
  a PDF CLI, sample.py, screenshots, result/review files, or CSV output.
- Return every physical row as one ordered rectangular `rows` matrix. Never
  emit a separate header. Preserve source text as strings, including leading
  zeros, signs, units, and all fragments of a visible cell.
- Decide the extraction logic from the combined native evidence. Do not assume
  that every source block, cell bbox, vector line, or word grouping is correct;
  do not assume that a table is ruled or unruled. When evidence conflicts,
  compare it with the screenshot and target bbox and choose the simplest robust
  interpretation supported by this table.
- For a merged visible cell, place its text in the leftmost logical column it
  covers and leave the other covered columns blank. This is an output-shape
  convention, not header detection.
- Do not execute either generated script. Runtime owns execution and review.

{{RUNTIME_CONTEXT}}

## Final execution reminder

First complete the screenshot-only sample, then use exactly
`latestGeometry.revision` for parser planning. Return that exact value in
`geometryRevisionUsed`. Return only the schema JSON containing complete scripts.
