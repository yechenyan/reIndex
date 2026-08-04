# pdf-extractor-pdf

`pdf-extractor-pdf` is a deterministic workflow around four isolated Agent
roles: orchestration/review, visual discovery, extractor authoring, and visual QA.
The reusable package prepares evidence and enforces coverage, freezing,
provenance, validation, review, and final delivery gates.

It does not attempt to provide one universal PDF table parser. Each completed
project contains reusable extraction code for its exact PDF or declared family.

## Delivery layout

```text
project/
├── source.pdf
├── output/                 # final CSV files and result.json
└── extractor/              # every non-output deliverable
    ├── job.yaml
    ├── main.py             # stable run/check entry point
    ├── *.py                # PDF-specific rules and merge policy
    └── evidence/
        ├── pages-low/      # all-page thumbnails
        ├── contact-sheets/
        ├── inventory-overlays/ # full-page Segment BBox review images
        ├── pages-high/     # targeted escalations only
        ├── segments/       # frozen crops and geometry
        ├── inventory.json
        ├── reference.json
        ├── reference-work/ # QA structure and adaptive sample templates
        ├── agent-tasks/    # role-scoped briefs
        ├── review.json     # compact evidence packet for the main Agent
        ├── role-separation.json
        ├── final.json
        └── metrics/        # CLI and Agent timing/usage records
```

## Commands

```bash
pdf-extractor-pdf init PROJECT SOURCE --request "Extract all tables"
pdf-extractor-pdf prepare PROJECT/extractor/job.yaml
pdf-extractor-pdf render-pages PROJECT/extractor/job.yaml 4 16 17
pdf-extractor-pdf audit-inventory PROJECT/extractor/job.yaml inventory-draft.json
pdf-extractor-pdf freeze-inventory PROJECT/extractor/job.yaml inventory-draft.json
pdf-extractor-pdf inspect PROJECT/extractor/job.yaml
pdf-extractor-pdf scaffold-reference PROJECT/extractor/job.yaml
pdf-extractor-pdf plan-reference PROJECT/extractor/job.yaml reference-structure-draft.json
pdf-extractor-pdf freeze-reference PROJECT/extractor/job.yaml reference-draft.json
pdf-extractor-pdf run PROJECT/extractor/job.yaml
pdf-extractor-pdf validate PROJECT/extractor/job.yaml
pdf-extractor-pdf repair-scope PROJECT/extractor/job.yaml --route extraction_agent
pdf-extractor-pdf resolve-merges PROJECT/extractor/job.yaml merge-decisions.json
pdf-extractor-pdf finalize PROJECT/extractor/job.yaml
pdf-extractor-pdf verify-cache PROJECT/extractor/job.yaml
```

`validate` runs the project extractor twice, writes the output, compares the
independently frozen reference, validates row-level provenance, proposes only
continuity-evidenced logical-table merge candidates, and creates a compact JSON
evidence packet for the main Agent. Failed reviews can be rerun after editing `main.py`; QA changes require
`reopen-reference`, and logical table changes require `reopen-inventory`.
`resolve-merges` freezes a source-evidenced main-Agent `keep_separate` decision;
confirmed merges still require reopening Inventory. `check` verifies the latest
review and output hashes without rerunning extraction, while `verify-cache`
non-mutatively verifies neutral evidence even after completion.

`prepare` creates rolling eight-page contact sheets with one-page overlap, so a
possible continuation is visible in two consecutive sheets. Inventory freezing
requires a two-pass `audit-inventory`: fixed code creates full-page BBox overlays
and edge diagnostics, then Finder records each overlay hash after reviewing all
four edges. Failed reviews are grouped into table-level cases. Before any repair
dispatch, `repair-scope` freezes the affected table IDs; Agent briefs expose only
that scope and validation rejects changes to unaffected Inventory, reference, or
result tables. QA reference repair templates contain only affected tables, while
fixed code reuses the unaffected frozen reference entries.

The package launches extractor code in a controlled subprocess with a timeout,
fixed hash seed, isolated temporary result path, and bytecode disabled. This is
process isolation, not a security boundary; untrusted code still requires the
caller's OS/container sandbox.

## Agent workflow

The bundled skill is the normative orchestration guide:

```bash
pdf-extractor-pdf skill-path
pdf-extractor-pdf install-skill /path/to/workspace
```

Every CLI call appends exact wall time to
`extractor/evidence/metrics/commands.jsonl`. Agent runtimes should submit their
own timing, model, conversation count, and token telemetry with `record-agent`.
When a host does not expose token usage, record `token_usage: null`; never invent
an exact count.

For identity and parallel-role gates, bracket Agent work with `stage-start` and
`stage-finish`, then run `metrics-report`. The summary keeps both summed Agent
time and the parallel wall-clock envelope, so simultaneous extraction and QA are
not misreported as serial elapsed time.

```bash
pdf-extractor-pdf stage-start JOB extraction --role extraction_agent --model MODEL --run-id extraction-1 --agent-id AGENT-A
pdf-extractor-pdf stage-start JOB qa --role qa_agent --model MODEL --run-id qa-1 --agent-id AGENT-B
pdf-extractor-pdf stage-finish JOB extraction-1
pdf-extractor-pdf metrics-report JOB
```

Each `stage-start` is one real Agent dispatch. `stage-finish` derives conversation
and repair counts from recorded dispatch history; children do not self-report
those values. Start a new run ID before every routed follow-up.
