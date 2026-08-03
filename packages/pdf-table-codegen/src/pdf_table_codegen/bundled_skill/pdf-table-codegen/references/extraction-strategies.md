# Extraction strategy selection

Choose a strategy after the table inventory is frozen. Decide independently for
each table or stable layout family. Combining strategies in one extractor is
normal; never reshape the source merely to fit a helper.

## Native-text strategies

- Use fixed row bands and column edges for stable rectangular layouts whose word
  coordinates stay inside reliable cell boundaries.
- Use anchors plus line/column clustering for borderless tables, variable row
  heights, or layouts where coordinates move but labels and reading order remain
  stable.
- Use vector drawings to reconstruct cells when visible rules are more reliable
  than text spacing. Assign native words to the reconstructed cells afterward.
- Use block/span reading order and table-specific state machines for hierarchical
  rows, grouped sections, multi-level headers, or semantic continuations.
- Use native table detectors only as posterior geometry hints. Validate their
  boundaries against the frozen inventory and source-derived reference.
- Use explicit per-table corrections for known source encoding defects. Keep
  those corrections outside shared text helpers so they cannot affect other
  tables.

## Fallbacks

- Mix methods across pages or regions when a logical table changes layout.
- Use local OCR only when native words in a frozen region are absent or unusable;
  do not replace usable native text globally.
- Write a direct special-case parser when that is clearer and safer than a
  premature abstraction. Generated project code is allowed to be document-specific.

## Required failure checks

In addition to row and column counts, assert the source properties that make the
chosen strategy safe: expected anchors, row identifiers, boundary words, page
continuations, non-empty key columns, or stable coordinate ranges. Fail loudly
when those invariants change. Keep the independent visual reference as the final
strategy-neutral quality gate.
