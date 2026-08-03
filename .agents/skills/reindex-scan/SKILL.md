---
name: reindex-scan
description: Scan raw files into ReIndex when the user asks to scan, compile, ingest, or convert local data.
---

# ReIndex scan

1. Run `rei inspect <path>` and review effective inputs, relationships and changes.
2. Apply only evidence-backed manifest corrections; never delete raw files just to pass validation.
3. Run `rei scan <path>` and review changes, warnings and generated Node cards.
4. Curate new or stale cards once per source document, not with one Agent pass per Node:
   - read the document outline and its ordered text contents once;
   - describe text objectively and retain all non-redundant content points needed to identify it;
   - preserve the CLI-generated section path and page location;
   - for tables, preserve the generated field statistics and Preview, then add only grounded descriptions of what the table records, its explicit relation to other tables, and how the source text uses it;
   - do not evaluate content, infer trends, rank values, or add generic usage advice;
   - do not perform additional visual analysis for images; retain caption, position, dimensions, OCR, and nearby source text only.
5. Edit Markdown card bodies only. The CLI owns YAML frontmatter. Remove boilerplate and avoid repeating metadata already visible in the card.
6. Run `rei check <path>` after card edits.
7. Report whether all affected source documents were reviewed, plus the Collection name, Node count, warnings and package location. Passing checks is not human approval.
