# Job format

Use one folder per PDF:

```text
pdf-folder/
├── source.pdf
└── project/
    ├── job.yaml
    ├── extractor.py
    ├── evidence/
    │   ├── manifest.json
    │   ├── inventory.frozen.json
    │   ├── visual-reference.json
    │   ├── contacts/
    │   ├── pages/
    │   ├── geometry/
    │   ├── tables/                # frozen-region crops and neutral geometry
    │   └── assertion-hints.json  # QA hints, never extraction input
    └── output/
```

Minimal configuration:

```yaml
spec: pdf-table-codegen/job@1.0
name: example
source: ../source.pdf
extractor: ./extractor.py
evidence_dir: ./evidence
inventory: ./evidence/inventory.frozen.json
reference: ./evidence/visual-reference.json
output_dir: ./output
evidence:
  page_dpi: 144
  contact_pages: 12
policy:
  compatibility: exact
```

Resolve all paths relative to `job.yaml`. Keep schema, normalization,
compatibility, and extraction decisions together in `extractor.py`; do not create
separate configuration files unless the document genuinely requires maintained
business data rather than code.

Keep temporary inventory/reference drafts outside `project/`. Freeze them with:

```bash
pdf-table-codegen freeze-inventory project/job.yaml /tmp/inventory-draft.json
pdf-table-codegen inspect project/job.yaml
pdf-table-codegen freeze-reference project/job.yaml /tmp/reference-draft.json
pdf-table-codegen scaffold project/job.yaml
```
