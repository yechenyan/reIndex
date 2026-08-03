# pdf-table-codegen

`pdf-table-codegen` is an Agent-oriented code generator workflow, not a universal
PDF table parser. It prepares neutral page evidence, then lets an Agent create a
small PDF-specific `extractor.py`. Later pipeline runs are deterministic and do
not require AI.

The package standardizes evidence, the runtime contract, provenance, and
verification—not the extraction algorithm. The Agent chooses a strategy per
table or layout family and may combine word geometry, anchors, clustering,
vector rules, native table hints, direct special cases, or local OCR. Fixed row
bands and column edges are optional, never required.

```bash
pdf-table-codegen prepare path/to/job.yaml
# Agent reviews evidence and writes temporary drafts
pdf-table-codegen freeze-inventory path/to/job.yaml /tmp/inventory.json
pdf-table-codegen inspect path/to/job.yaml
pdf-table-codegen freeze-reference path/to/job.yaml /tmp/reference.json
pdf-table-codegen scaffold path/to/job.yaml
# Agent chooses per-table strategies and writes extractor.py
pdf-table-codegen run path/to/job.yaml
pdf-table-codegen verify path/to/job.yaml
```

`prepare` uses a source/DPI/version cache only after verifying every evidence
hash. `inspect` runs only after inventory freeze and creates table crops plus
neutral word/drawing reports; it does not select a parser. Freeze commands add
and validate source hashes, inventory hashes, table IDs, sample coverage, and
continuation-boundary samples. Every command reports `elapsed_seconds`.

The generated extractor exposes the package-neutral API:

```python
from pdf_table_codegen import ExtractionRequest
from extractor import extract_tables

result = extract_tables(ExtractionRequest(source=pdf_path))
```

Each PDF project owns its input PDF, `job.yaml`, `extractor.py`, frozen evidence,
and output directory. The package is independently installable; ReIndex or any
other pipeline only needs a thin caller around the same function.
