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
        ├── finder-packet.json # ranked pages plus pre-rendered candidates
        ├── inventory-overlays/ # full-page Segment BBox review images
        ├── inventory-review.json # Finder edits booleans/edges only
        ├── pages-high/     # targeted escalations only
        ├── segments/       # frozen crops and geometry
        ├── inventory.json
        ├── reference.json
        ├── normalization-decisions.json # frozen visual line-wrap decisions
        ├── reference-work/ # QA structure and adaptive sample templates
        ├── agent-tasks/    # role-scoped briefs
        ├── review.json     # compact evidence packet for the main Agent
        ├── reviews/        # immutable numbered Review history
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
pdf-extractor-pdf begin-qa-repair PROJECT/extractor/job.yaml --tables table-5
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

Tables are header-neutral matrices. Inventory freezes positional `column_count`;
the first visible row is output as row 0 and is never implicitly promoted to a
header. CSV files contain the matrix rows once, without an extra field-name row.
QA declares each column position `exact` or `text`. Structure, row/column order,
provenance, and `exact` values remain strict. `text` comparison removes only
separator characters while preserving letter/digit order: line breaks, spaces,
and hyphens can produce a non-blocking `format_only` report, but missing or
reordered content still fails. Every empty QA sample cell must be explicitly
listed in `source_blank_indices` before the reference can freeze. Continuation
Segments record source rows and repeated leading rows separately, so only proven
repetitions are removed during merge.
Every table samples its first three rows, last two rows, middle row, and both
sides of Segment boundaries; duplicate indices are collapsed.

`prepare` creates rolling eight-page contact sheets with one-page overlap and a
Finder packet with code-ranked, pre-rendered candidate pages. In one dispatch,
Finder writes its draft, runs `audit-inventory`, fixes blocking BBoxes, attests
the visibility and four reviewed edges, and reruns until the audit passes.
Failed reviews are grouped into table-level cases. Before any repair
dispatch, `repair-scope` freezes the affected table IDs; Agent briefs expose only
that scope and validation rejects changes to unaffected Inventory, reference, or
result tables. QA reference repair templates contain only affected tables, while
fixed code reuses the unaffected frozen reference entries.

After Segment geometry exists, `scaffold-reference` lists each distinct token
ending in `-` at a visual line boundary with the next line's first token. A
standalone fixed function classifies obvious lowercase continuation as `remove`
and uppercase/digit continuation as `keep`; QA marks only ambiguous candidates.
Fixed code applies decisions to matching cells. Soft hyphens are removed
deterministically.

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
pdf-extractor-pdf stage-cancel JOB qa-1 --reason "dispatch did not occur"
pdf-extractor-pdf metrics-report JOB
```

Each `stage-start` is one recorded dispatch or orchestration step; pass
`--dispatch-kind spawn`, `followup`, or `orchestrator`. The report counts only
child `spawn/followup` records as Agent conversations and reports main-Agent
records separately as orchestration steps. Start a new run ID before every routed follow-up.
The same `agent_id` cannot have two unfinished stages, preventing overlapping
self-time from inflating totals. `begin-qa-repair` is resumable and performs
scope, reopen, partial template, and brief refresh as one operation. Every
validation archives `reviews/review-NNN.json`; reopening keeps that history.
If a stage was opened but no real Agent dispatch occurred, cancel it instead of
counting a phantom conversation. After a passed/finalized review, an independent
source audit may create an explicit `repair-scope --tables ...`; validation still
protects every table outside that narrowly reopened scope. Extraction-only
post-final repairs validate directly without reopening an unchanged QA reference.
