---
name: reindex-scan
description: Scan raw files into ReIndex when the user asks to scan, ingest, convert raw to ReIndex, or run rei scan.
---

# ReIndex scan

1. Run `rei inspect <path>` to resolve the exact Collection, scope, effective inputs, profiles,
   relationships and changes.
2. Compare the root `reIndex.md` with real files. Keep it unchanged when correct. Apply only minimal,
   evidence-backed fixes; ask about ambiguous provenance, page or ignore decisions. Do not delete raw files
   or remove declarations merely to make scan pass.
3. Do not delete or replace `.rei/collection.json` or `.rei/identities.json` unless the user explicitly
   requests a new Collection identity. Run inspect again only when the manifest changed.
4. Run `rei scan <path>` and review its changes, review, warnings and package path.
5. Review generated content and Node cards. Edit Markdown bodies only; CLI owns YAML frontmatter.
6. Run `rei check <path>` after card-body edits. Run scan again only after source, manifest or structure
   changes. Skip check when scan succeeded and no package files were edited.
7. When scanning a repository fixture, run its documented project tests; `rei check` validates the package
   but does not replace repository acceptance tests.
8. Report package path, Node count, changes and warnings briefly. Passing checks do not imply human approval.
