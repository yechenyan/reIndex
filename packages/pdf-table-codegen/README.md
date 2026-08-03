# pdf-table-codegen

`pdf-table-codegen` coordinates independent Agents and deterministic tools to
create reusable, PDF-specific table extractors. AI is required only for the
one-time discovery, QA transcription, and extractor authoring workflow. Later
pipeline runs execute project-local Python without AI.

The package owns workflow state, neutral evidence, inventory comparison,
freezing, verification, provenance, and final gates. It does not prescribe a
universal PDF table parser.

## Roles

- **Main Agent:** clarifies requirements, reviews inventory conflicts, and owns
  the final machine-complete gate.
- **Execution Agent:** independently discovers tables and writes `extractor.py`.
- **QA Agent:** independently discovers tables and freezes source-derived QA
  samples without seeing extractor code or output.
- **Code:** prepares evidence, diffs drafts, freezes artifacts, renders crops,
  verifies results, and checks deterministic double runs.

## Workflow

```bash
pdf-table-codegen prepare project/job.yaml

# Execution and QA Agents independently write drafts outside the project.
pdf-table-codegen compare-inventories \
  project/job.yaml /tmp/inventory-execution.json /tmp/inventory-qa.json

# Main Agent reviews only conflicts and writes the reconciliation.
pdf-table-codegen freeze-inventory project/job.yaml /tmp/reconciliation.json
pdf-table-codegen inspect project/job.yaml

# Execution Agent writes extractor.py while QA Agent writes its isolated draft.
pdf-table-codegen freeze-reference project/job.yaml /tmp/reference-qa.json

# verify runs the extractor twice and performs all inventory/reference/QA checks.
pdf-table-codegen verify project/job.yaml

# Main Agent checks the report and unresolved warnings.
pdf-table-codegen finalize project/job.yaml /tmp/final-review.json
```

`run` is available after the QA reference is frozen. `status` exposes workflow
phase and history. `reopen-inventory` and `reopen-reference` explicitly
invalidate downstream artifacts; frozen files must never be edited silently.
Running output again after verification also invalidates the old verification
and final review, so the project must pass `verify` and `finalize` again.

Source-document table merging, splitting, and false-positive removal belong in
the main-agent reconciliation before inventory freeze. Business output merging
or filtering belongs in `job.yaml` requirements and project-local extractor
code; real source tables remain in the inventory.

## Runtime API

```python
from pathlib import Path
from pdf_table_codegen import ExtractionRequest
from extractor import extract_tables

result = extract_tables(ExtractionRequest(source=Path("input.pdf")))
```

Every extracted row must include provenance. Unknown source hashes are rejected
by default. CSV is one serializer; `ExtractionResult` is the pipeline boundary.
