---
name: pdf-extractor-pdf
description: Build a reusable PDF-specific table extractor with full-page visual discovery, frozen inventory, independent QA, row provenance, deterministic validation, and review gates. Use when asked to extract tables from a PDF into a project-local output plus reusable extractor.
---

# PDF Extractor PDF

This workflow combines Agent judgment with fixed code gates. Preserve all
deliverables under the target project: only final tables belong in `output/`;
everything else belongs in `extractor/`. Do not copy package source into the
project.

Read `references/formats.md` before creating inventory or reference drafts. Read
`references/extraction.md` before authoring the extractor.

## Non-negotiable role isolation

- The main Agent clarifies requirements, creates the job, resolves ambiguous
  review findings, and owns finalization.
- The finder Agent visually checks every page and writes the inventory draft.
- The extraction Agent sees the frozen inventory and segment evidence, then
  writes `extractor/main.py` and optional helpers/merge policy.
- The QA Agent independently reads only source segment images and neutral
  geometry. It must not read extractor code, generated output, prior answers, or
  reference files from another run.
- Fixed code owns hashes, page coverage, freeze gates, evidence generation,
  execution, deterministic double run, reference comparison, provenance,
  merge-candidate detection, and reports.

Use four separate roles by default: main, finder, extraction, and QA. Finder is
a serial prerequisite; extraction and QA start in parallel only after Inventory
freeze and `inspect`. Do not merge finder with extraction merely to save a turn:
record that exception only for a deliberately simplified run or when separate
Agents are unavailable.

The default policy requires four distinct `agent_id` values and overlapping
extraction/QA stage intervals. A reduced-isolation run requires an explicit job
policy waiver and must record that limitation; it cannot silently pass the
four-role gate.

## Stage 1: clarify and initialize

Ask only questions whose answers materially change which tables, output form,
normalization, or merge behavior is correct. Otherwise state reasonable
assumptions. Then run:

```bash
pdf-extractor-pdf init PROJECT SOURCE --request "..."
```

Inspect and edit `extractor/job.yaml` if needed. Never place generated evidence
or code beside the package source.

## Stage 2: neutral preparation

Run `prepare`. Confirm the source hash, page count, every low-resolution page,
all contact sheets, `finder-packet.json`, and page metadata exist. Contact sheets use rolling page
windows: the first page of each new sheet repeats the previous sheet's last page.
Use this overlap to judge cross-page continuation. Contact sheets are a recall
tool, not sufficient evidence for tiny or ambiguous tables. Start with the
packet's pre-rendered candidate pages; call `render-pages` only for remaining
uncertain pages.

## Stage 3: discovery and hard gate 1

The finder Agent must inspect every page and label it `table`, `no_table`,
`continuation`, or `uncertain`. Group physical segments into logical tables,
freeze each positional `column_count`, and record every Segment bbox. A table is
a header-neutral matrix: row 0 is an ordinary source row. For `uncertain` or suspicious pages, use
`render-pages` only for those pages and reinspect them.

In the same Finder dispatch, write the draft, run `audit-inventory JOB DRAFT`,
fix blocking bboxes, edit only `all_visible_table_content_inside` and
`reviewed_edges` in `inventory-review.json`, and rerun until it passes. Finder
returns one freeze-ready result; do not use separate repair/attestation turns.

Freeze only when there are no uncertain pages. The code rejects incomplete page
coverage, invalid Segment geometry, or mismatches between page labels and
Segments. Treat `inventory.json` as immutable after freezing. Logical table
merges/splits require `reopen-inventory --reason ...`.

## Stage 4: two independent branches

Run `inspect` to create high-resolution crops and neutral word/line geometry for
every frozen Segment. It fingerprints each Segment and automatically reuses
unchanged evidence after a local Inventory repair; do not manually select a
`--segments` list.

In parallel when possible:

1. The extraction Agent selects a strategy per layout group, implements
   `extract(source, inventory)`, returns `column_count` plus string rows, performs
   actual cross-page merge rules, removes only proven repeated leading rows and
   page footers, joins broken rows, preserves Segment order, and emits
   page/BBox/Segment provenance for every row. Do not invent column names or a
   separate header array. Project-generated extractor files have no artificial
   200-line limit.
2. The QA Agent runs `scaffold-reference`, confirms frozen positional
   `column_count`, assigns `exact` to numeric/date/ID/code/amount positions and
   `text` to free-text positions, and records source rows and repeated leading
   rows per Segment. Fixed code classifies obvious visual hyphen wraps; QA marks
   only unresolved candidates `keep` or `remove`, then runs `plan-reference`. Fixed code
   calculates the adaptive first-three/last-two/middle/boundary indices. QA fills the
   generated sample cells from the original frozen crops and freezes it.

Start distinct `extraction` and `qa` telemetry runs before dispatching these
branches, and finish each run independently when its Agent returns.

Freeze the QA draft only after completing all required samples. Do not derive
reference values from the extractor or output. List every genuinely empty
sample cell in `source_blank_indices`; an undeclared blank must not freeze.

## Stage 5: execute and compare

Use `run` only as an optional development smoke test. Run `validate` for the authoritative
double run. Give `review.json` to the main Agent. It groups raw issues into one
case per table/Segment root cause and contains
only cited source crops, matched Extractor/QA sample rows, raw/normalized cell
differences, deterministic routes, and continuity-evidenced merge questions.
`format_only` entries are non-blocking raw display differences in `text`
column positions. Never route them as content repairs. Text comparison ignores separator
characters but preserves letter/digit order; missing or reordered text still fails.
Distinct table numbers/titles are strong merge contradictions; column widths
alone must never create or confirm a merge candidate.
Do not raise the merge threshold to bypass a candidate. For a visually confirmed
false positive, freeze a reasoned `keep_separate` decision with `resolve-merges`
and rerun `validate`. A real merge still requires reopening Inventory.

## Stage 6: grouped repairs

Before dispatching a repair, run `repair-scope JOB --route ROLE`; for an ambiguous
main-Agent decision, also pass `--tables ID ...`. Rerun `agent-briefs`. The public
scope and briefs expose only affected table IDs/evidence. Fixed validation hashes
unaffected Inventory, reference, and result tables and fails on any change.

Repair every affected table of the same type in one pass:

- `extraction_agent`: extraction Agent changes code, then rerun `validate`.
- `main_agent`: main Agent checks the cited source crop and decides which side is
  wrong; edit code or reopen/fix the reference.
- unclear evidence: rerender only affected pages/Segments at higher DPI.
- confirmed merge/split: reopen Inventory, update only affected logical tables,
  refreeze, inspect, regenerate affected code/reference, and validate again.

Never ask an Agent to reread or regenerate a passing table. After Inventory or
QA repair, `scaffold-reference` and `plan-reference` automatically include only
the active scope; fixed code merges those entries with unaffected frozen QA data.
Use the resumable `begin-qa-repair` to atomically freeze the QA scope, reopen the
reference, generate its partial template, and refresh briefs. Repeating it after
an interruption resumes the same table scope. Pure line-wrap corrections
change frozen normalization decisions and are applied by fixed code; do not
rerun the extraction Agent.

If an independent source audit finds a shared QA/extractor error after a passed
or finalized review, create an explicit `repair-scope --tables ID ...` and route
only those tables. This post-review escape hatch must not broaden scope from old
review cases; all unlisted tables remain hash-protected. An extraction-only
repair can validate directly from `complete`; do not reopen an unchanged QA
reference merely to move the workflow phase.

Do not weaken a reference merely to make output pass.

## Stage 7: hard gate 2

Every validation writes an immutable numbered JSON under `evidence/reviews/`
and refreshes `review.json` as the latest pointer; reopening preserves history.
Run `finalize` only when validation passes and no merge candidate meets the job
threshold. Confirm `output/` contains the intended tables and `extractor/`
contains code, evidence, reports, and metrics. Machine completion is not human
approval.

After finalization, run the non-mutating `verify-cache`; do not reopen Inventory
just to test cache integrity. Use `check` for a non-executing verification of the
latest review and output hashes.

## Telemetry and feedback

The CLI records command wall time automatically. Record each real Agent dispatch
with a new `stage-start` run ID, set `--dispatch-kind` to `spawn`, `followup`, or
`orchestrator`, and close it with `stage-finish`, using role,
model, waiting time, and host-reported token usage. Only child dispatches count
as Agent conversations; main-Agent records are orchestration steps. Children do
not self-report either value. Run
`stage-cancel JOB RUN_ID --reason ...` when a stage was opened but the Agent was
never actually dispatched; cancelled stages are retained as audit evidence but
are excluded from conversation and timing totals. Run
`metrics-report` at the end; it computes
command totals, summed Agent time, parallel wall-clock envelope, active/waiting
time, child conversations/follow-ups by role, main orchestration steps, and token availability. If exact token telemetry
is unavailable, leave token arguments absent so usage remains null. One
`agent_id` may not start a new stage until its prior stage ends or is cancelled.

Finish with measured stage timings, redundant/missing steps, quality risks,
blockers, child conversation count, main orchestration steps, token availability,
and concrete time/quality improvements.
