---
name: reindex-scan
description: Scan raw files into ReIndex when the user asks to scan, compile, ingest, or convert local data.
---

# ReIndex scan

1. Run `rei inspect <path>` and review effective inputs, relationships and changes.
2. Apply only evidence-backed manifest corrections; never delete raw files just to pass validation.
3. Run `rei scan <path>` and review changes, warnings and generated Node cards.
4. Edit Markdown card bodies only. The CLI owns YAML frontmatter.
5. Run `rei check <path>` after manual card edits.
6. Report the Collection name, Node count, warnings and package location. Passing checks is not human approval.
