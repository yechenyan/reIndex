# Same-session physical-row repair

Continue the same table session. Runtime does not resend the screenshot or the
inline native geometry: use the evidence already present in this session. Return
`action="ready"`, complete scripts, and the same `geometryRevisionUsed`.

There is no header/body distinction. Physical row 1 is the top visible row in
both sample and parser, and parser output is only `{"rows": [...]}`.

## Mandatory conflict order

When `repairMode="visual_recheck"`:

1. Re-read every reported physical row/cell/count from the existing whole-table
   screenshot. The screenshot—not parser output or geometry—decides whether the
   sample is right.
2. If sample.py is wrong or incomplete, correct its `SAMPLE` literal, keep
   parse.py unchanged, and return. Runtime will review the complete result again.
3. If sample.py is visually correct, keep it unchanged and repair parse.py using
   the existing native geometry and previous generated table.

Never weaken correct parser text to fit a mistaken sample, and never copy
`generatedTable` into sample.py without visual confirmation.

When the first sampled rows match and every sampled last-row value exists in the
parser but the last rows are shifted by exactly one physical position, treat the
visual `totalPhysicalRows` count as suspect before assuming a missing parser row.
Recount horizontal row bands in the existing screenshot from the two fixed table
edges; do not infer an extra row from row labels or from the prior sample count.

When `repairMode="code_repair"`, repair the script identified by the collected
syntax, execution, contract, empty-row, shape, or cell-level errors. The previous
screenshot and geometry remain available in session if needed, but do not ask
Runtime to resend them.

For every repair, inspect all supplied errors together before answering. Return
complete scripts, not patches. Check syntax, names, branches, return values, and
the fixed entries. Never hard-code sampled values in parse.py or read sample,
result, review, CSV, screenshot, or geometry files.

Keep the fixed sample entry unchanged except for `SAMPLE`:

```python
from pdf_parse.generated_runtime import emit_sample, load_sample_args

SAMPLE = {"mode": "sample", "rows": [], "totalPhysicalRows": 0,
          "compareRules": [], "skipReason": ""}

if __name__ == "__main__":
    load_sample_args()
    emit_sample(SAMPLE)
```

Keep the fixed parser entry unchanged:

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

`liteparse_page(context, page_number)` is the single runtime geometry API. It
returns native LiteParse 2.13 objects with OCR disabled. Words use direct
`word.x/y/width/height`, not `word.bbox`; TextItems, vector lines/shapes, and
blocks are available directly on the returned page. Runtime `block.bbox` and
`cell.bbox` are non-subscriptable `AnnotationRect` objects; use their direct
`.x/.y/.width/.height` attributes. Compact inline bbox arrays exist only in the
original prompt evidence. Runtime `block.rows` is an ordered list of cell lists,
not row objects; rows have no `.index`, so iterate or enumerate the list directly.
Choose the table strategy
from that evidence instead of relying on Runtime-side table heuristics.
