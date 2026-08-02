---
name: reindex-create
description: Initialize a ReIndex project when the user asks to set up ReIndex or run rei init/create.
---

# ReIndex create

1. Resolve the exact directory named by the user.
2. Prefer `rei init <directory> --agent <current-agent>` for normal setup. It is idempotent and manages skills.
3. Use `rei create <directory>` only when identity-only initialization was explicitly requested.
4. Report the Collection name and whether it was created or reused. UUID is internal and normally omitted.
5. Do not scan, push, delete source files, or replace `.rei/collection.json` during initialization.
