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

Every logical table returns its frozen ID, title, ordered columns, string rows,
and one provenance item per row. A provenance item contains a 1-based PDF page,
row bbox in PDF points, and frozen Segment ID. The row bbox must lie inside its
Segment bbox.

Cross-page merge policy is executable project code, not an informal note. It
should explicitly remove repeated headers and page footers, join only proven
split rows, keep Segment order, and retain the original page and row bbox. Add
source-hash and layout assertions so a changed PDF fails loudly.

Normalization should be conservative and declared. Preserve IDs, leading zeros,
decimal punctuation, units, symbols, empty cells, and source-language spelling
unless the job explicitly requests normalization. A visual glyph can be more
reliable than a defective embedded text layer; document any such correction in
code and evidence.
