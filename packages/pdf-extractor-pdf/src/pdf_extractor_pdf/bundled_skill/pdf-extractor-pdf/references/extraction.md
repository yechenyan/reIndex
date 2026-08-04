# Extraction strategies and output contract

Choose independently for each layout group. Useful strategies include native
word geometry with fixed or inferred bands, vector-line grid reconstruction,
anchor clustering, state machines for wrapped rows, targeted native table
detection after Inventory freeze, and local OCR only when the PDF lacks a usable
text layer. Avoid whole-document parser candidate unions during discovery.

The project `main.py` exposes:

```python
def extract(source: Path, inventory: dict) -> ExtractionResult:
    ...
```

Every logical table returns its frozen ID, title, positional `column_count`,
string rows, and one provenance item per row. There is no header array: a visual
header, a blank leading row, or a data row at the top is preserved as row 0. A provenance item contains a 1-based PDF page,
row bbox in PDF points, and frozen Segment ID. The row bbox must lie inside its
Segment bbox.

Cross-page merge policy is executable project code, not an informal note. It
should explicitly remove only repeated leading rows and page footers, join only proven
split rows, keep Segment order, and retain the original page and row bbox. Add
source-hash and layout assertions so a changed PDF fails loudly.

Normalization should be conservative and declared. Preserve IDs, leading zeros,
decimal punctuation, units, symbols, empty cells, and source-language spelling
unless the job explicitly requests normalization. A visual glyph can be more
reliable than a defective embedded text layer; document any such correction in
code and evidence.

Wrong row counts, positional column order, cell placement, or missing values are extraction
defects: repair the affected table's generated code. Validation remains strict
for structure and `exact` columns. Free-text `text` columns use an
order-preserving alphanumeric content key, so separator-only differences are
reported as `format_only` without triggering a repair; reordered or missing text
still fails.

Do not implement source line-wrap dehyphenation in generated extractor code.
The standalone fixed normalizer removes soft hyphens and classifies obvious
lowercase continuations as `remove` and uppercase/digit continuations as `keep`.
QA freezes only ambiguous `keep`/`remove` decisions; the runner applies all
decisions to matching cells.
