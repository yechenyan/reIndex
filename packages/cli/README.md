# ReIndex CLI

`rei` compiles local files into validated ReIndex 1.0 packages. `reindex` is an alias.

## Commands

```bash
rei create <collection-dir>
rei inspect <path>
rei scan <path> [--collection-root <collection-dir>]
rei check <path>
```

- `create` writes or reuses the stable Collection identity under `.rei/` and reports `created: true|false`.
- `inspect` resolves the nearest Collection and reports effective inputs, CSV/PDF profiles, relationships,
  ignored items and changes without writing or loading Docling layout/OCR models.
- `scan` parses files, validates a staging package, and publishes it atomically.
- `scan` returns complete changes, review categories and warning details.
- `check` validates the current package, detects edits to CLI-owned metadata, and marks newly added raw
  inputs as stale.

The first PDF scan initializes Docling's local layout models. PDFs with a usable text
layer run with OCR disabled; image-only PDFs retry with Docling OCR. Parse artifacts are
cached under `.rei/cache/` and may be deleted without losing Node identity.

`reIndex.md` is optional and remains the only authoring manifest. Agent edits should be
minimal and evidence-backed. CLI owns Node frontmatter; the Markdown card body is
curator-owned and survives later scans by stable Node ID.
