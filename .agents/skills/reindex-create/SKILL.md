---
name: reindex-create
description: Create a ReIndex Collection identity when the user asks to initialize a Collection or run rei create.
---

# ReIndex create

1. Resolve the directory the user named; do not guess an ambiguous Collection boundary.
2. Run `rei create <collection-dir>`. The command is idempotent and returns `created: true|false`.
3. Report the Collection root, ID, and whether the identity was created or reused.
4. Do not delete an existing `.rei/collection.json`, scan, create `reIndex.md`, or edit raw files as part
   of create. A new identity requires an explicit user request.
