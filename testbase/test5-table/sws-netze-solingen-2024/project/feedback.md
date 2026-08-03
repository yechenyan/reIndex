# pdf-table-codegen 0.3.0 rerun feedback

This was a fresh `job@2.0` acceptance run. Historical v1 artifacts were not
accepted as evidence. The v2 workflow reached `machine_complete` with six
logical tables, seven physical segments, 56/56 verification checks, passing
runtime QA, complete row provenance, and a deterministic internal double run.

## What worked

- Cold `prepare` generated evidence without running a table detector in 1.783s.
- Execution and QA independently found the same six source tables.
- `compare-inventories` exposed all identity and geometry differences before
  extraction work began.
- Exact phase gates prevented QA from being frozen after output creation.
- `verify` performed two extractor runs and checked deterministic structured
  results, inventory order, reference samples, runtime QA, hashes, and output.
- `reopen-reference` preserved the evidence trail for the one QA correction.
- `finalize` rechecked verified inputs and output hashes before recording
  `machine_complete_not_human_approved`.

## Bottlenecks and implementable fixes

1. **P0 — Canonical identity during discovery.** The two agents found the same
   six tables but generated 13 conflicts because one used descriptive IDs and
   the other used `table-1` style IDs. Add an optional source identity key based
   on page/segment fingerprints, or let compare suggest aliases while still
   requiring main-agent approval. This would preserve independence without
   turning naming differences into six add/delete pairs.

2. **P0 — Reference-draft preflight/template.** The isolated QA first emitted a
   `references` key instead of `tables`. Provide a generated
   `reference-draft@2.0` template plus a `validate-draft` command so structural
   failures are caught before `freeze-reference`.

3. **P0 — Source and normalized value support.** QA correctly needed both native
   `source_values` and visually faithful `normalized_values`, but the initial
   validator only consumed `values`. The generic validator was repaired during
   this run. Keep regression tests covering empty strings, native encoding
   defects, and source/normalized pairs.

4. **P1 — Make normalization policy explicit in the job.** Page 16 renders
   `I + II` while the native text layer encodes `| + ||`. Add job-level policies
   distinguishing Unicode/encoding repair, visual line-break normalization, and
   business transforms. Reference and extractor should name the same policy.

5. **P1 — Report the actual failure phase.** The first failing `verify` CLI
   response labeled its phase `verified`, while `workflow.json` correctly
   remained `reference_frozen`. Derive CLI phase from workflow state so operators
   do not mistake a failed attempt for a completed gate.

6. **P1 — Structured isolated-agent progress.** Approximately 130 seconds were
   spent waiting for isolated inventory/reference completion. A compact progress
   protocol such as pages reviewed, tables remaining, and draft-validation state
   would make waits observable without exposing isolated content.

7. **P2 — Emit run metrics automatically.** CLI elapsed values and workflow
   timestamps are machine-readable, but active role time, wait time, repair
   rounds, and historical-run separation were assembled manually. `finalize`
   could emit a metrics skeleton derived from workflow history and command logs.

8. **P2 — Clarify source-faithful headers versus output schema.** The first two
   source tables have no visible header row, and Table 2 has two blank stub
   headers. The extractor therefore emits empty source-faithful headers. If
   semantic output headers are desired, they should be declared as a business
   transform in `job.yaml`, not inferred by QA or extractor code.

## Timing summary

- Fresh v2 wall time to `machine_complete`: about 33m50s.
- Inventory discovery and comparison: about 5m19s wall, with independent QA.
- Conflict reconciliation and source-page checks: about 5m11s.
- Parallel extractor/reference work through first successful freeze: about
  13m43s after inspection, including two reference-schema repair rounds.
- Verification: first attempt 0.097s with one QA mismatch; final attempt 0.095s
  with 56/56 checks after one recorded reference reopen.
- Specialized tests, including the frozen SWS regression: 11 passed in 0.24s,
  about 0.7s wall.

Historical v1 timing was roughly 48 minutes and is recorded separately in
`run-metrics.json`; it is not part of this v2 acceptance result.
