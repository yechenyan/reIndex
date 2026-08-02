# ReIndex CLI

`rei` builds local files into ReIndex 1.0 packages and connects them to a ReIndex API. `reindex` is an alias.

## Install and initialize

Give an AI Agent this sentence:

> Run `uv tool install --upgrade reindex-cli`, then run `rei init <data-directory> --agent <current-agent>` to create or update the ReIndex skills.

`<current-agent>` is `codex`, `claude`, `cursor`, or `copilot`. `init` is idempotent, creates or reuses local identity, and installs or safely updates the three bundled skills. It does not scan, push, or download tutorial data.

```bash
rei init <collection-dir> [--name <name>] [--agent codex]
rei rename <collection-dir> <new-name>
```

## Local commands

```bash
rei inspect <path>
rei scan <path> [--collection-root <collection-dir>]
rei check <path>
```

`inspect` is read-only. `scan` stages, validates, and atomically publishes a package. `check` verifies package resources, protected Node metadata, and current inputs.

## Remote commands

```bash
rei set-api <base-url>
rei push [path] [--message <text>] [--dry-run]
rei fetch [path]
rei pull <name> [--output <directory>] [--version <version-id>]
rei pull --path <checkout>
rei history [path-or-name] [--version <version-id>]
rei diff [path] [--remote]
rei diff <name> --from <version-id> --to <version-id>
rei rollback <name> <version-id> [--message <text>] [--dry-run]
rei search "<query>" [--remote <name>] [--mode lexical|semantic|hybrid]
rei get <node-path> [--target card|source|content|asset] [--version <version-id>]
rei get raw://<path>
```

`push` sends a complete target manifest, uploads only missing SHA-256 blobs, and
atomically publishes a new version. A stale base is rejected; the server never
merges. `fetch` updates only remote metadata. `pull` creates or fast-forwards a
Node-only checkout; local/remote changes create `.rei/conflicts.json`, block
push, and require local resolution followed by `pull --continue`. `rollback`
publishes a retained manifest as a new head. Search always uses the active
version, while historical `pull` and `get` use `--version`.

Collection names are the user-facing remote identifier. UUIDs remain internal stable identity. Resource logical paths stay Collection-relative and are scoped by the internal Collection UUID.

## Skills

```bash
rei skills install --agent codex
rei skills update --agent codex
rei skills update --agent codex --force
```

Normal updates overwrite only unmodified ReIndex-managed copies. A modified skill reports a conflict unless `--force` is explicit.
