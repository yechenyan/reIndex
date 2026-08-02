---
name: reindex-data
description: Push, pull, search, and get exact ReIndex data when the user asks to publish or use remote ReIndex knowledge.
---

# ReIndex data

## Publish

1. Run `rei check <path>` before `rei push <path>`; scan first if stale.
2. `rei push` synchronously sends the validated package and exactly referenced sources.
3. Report the user-facing Collection name and ready status, not internal UUID details.

## Find and fetch

1. Use `rei search "<question>"` before downloading large files.
2. Select the result whose Evidence supports the task.
3. Use the result's Node path with `rei get <node-path> --target content`; use `source` only when original bytes are required.
4. Use `rei get raw://<path>` for an explicitly named raw source.
5. Answer from the fetched file and cite the Collection name and Node or raw path.

`rei pull <name>` downloads the complete Node tree only. It intentionally excludes source, content and assets; fetch exact resources later with `rei get`.
