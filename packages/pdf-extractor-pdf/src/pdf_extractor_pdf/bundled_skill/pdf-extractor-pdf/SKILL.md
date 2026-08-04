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
all contact sheets, and page metadata exist. Contact sheets use rolling page
windows: the first page of each new sheet repeats the previous sheet's last page.
Use this overlap to judge cross-page continuation. Contact sheets are a recall
tool, not sufficient evidence for tiny or ambiguous tables.

## Stage 3: discovery and hard gate 1

The finder Agent must inspect every page and label it `table`, `no_table`,
`continuation`, or `uncertain`. Group physical segments into logical tables and
record each Segment bbox. For `uncertain` or suspicious pages, use
`render-pages` only for those pages and reinspect them.

Before freezing, run `audit-inventory JOB DRAFT`. It creates a full-page overlay
for every Segment and reports clipped words plus lines/words near each edge.
Finder must inspect every overlay, then add its exact `overlay_sha256`, set
`all_visible_table_content_inside: true`, and list all four `reviewed_edges` in
the Segment `bbox_review`. Rerun `audit-inventory`; freeze only after it passes.

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
   `extract(source, inventory)`, performs actual cross-page merge rules, removes
   repeated headers/footers, joins broken rows, preserves Segment order, and
   emits page/BBox/Segment provenance for every row.
2. The QA Agent runs `scaffold-reference`, fills only columns and each Segment
   row count in the structure draft, then runs `plan-reference`. Fixed code
   calculates the adaptive first/last/middle/boundary indices. QA fills the
   generated sample cells from the original frozen crops and freezes it.

Start distinct `extraction` and `qa` telemetry runs before dispatching these
branches, and finish each run independently when its Agent returns.

Freeze the QA draft only after completing all required samples. Do not derive
reference values from the extractor or output.

## Stage 5: execute and compare

Use `run` only as an optional development smoke test. Run `validate` for the authoritative
double run. Give `review.json` to the main Agent. It groups raw issues into one
case per table/Segment root cause and contains
only cited source crops, matched Extractor/QA sample rows, raw/normalized cell
differences, deterministic routes, and continuity-evidenced merge questions.
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

Do not weaken a reference merely to make output pass.

## Stage 7: hard gate 2

Run `finalize` only when validation passes and no merge candidate meets the job
threshold. Confirm `output/` contains the intended tables and `extractor/`
contains code, evidence, reports, and metrics. Machine completion is not human
approval.

After finalization, run the non-mutating `verify-cache`; do not reopen Inventory
just to test cache integrity. Use `check` for a non-executing verification of the
latest review and output hashes.

## Telemetry and feedback

The CLI records command wall time automatically. Record each real Agent dispatch
with a new `stage-start` run ID and close it with `stage-finish`, using role,
model, waiting time, and host-reported token usage. Conversation count is the
number of recorded dispatches; repair count is derived from later dispatches of
the same real Agent identity. Children must not self-report either value. Run
`metrics-report` at the end; it computes
command totals, summed Agent time, parallel wall-clock envelope, active/waiting
time, conversations, repairs, and token availability. If exact token telemetry
is unavailable, leave token arguments absent so usage remains null.

Finish with measured stage timings, redundant/missing steps, quality risks,
blockers, repair rounds, conversation count, token availability, and concrete
time/quality improvements.
