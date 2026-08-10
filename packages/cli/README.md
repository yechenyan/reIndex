# ReIndex

The `reindex` distribution provides the ReIndex Python package and the `rei`
CLI.

The CLI is contract-first. Its authoritative interface is
[`src/reindex_cli/contract/reindex-cli-v1.yaml`](src/reindex_cli/contract/reindex-cli-v1.yaml).
Click commands and the Web reference are compiled from that contract; business
handlers implement behavior but cannot add arguments or options.

After changing the interface, regenerate and verify the Web artifact:

```bash
uv run python scripts/compile_cli_contract.py
uv run python scripts/compile_cli_contract.py --check
```

## Install and initialize

Give an AI Agent this sentence:

> Run `uv tool install --upgrade reindex`, then run `rei init <data-directory> --agent <current-agent>` to create or update the ReIndex skills.

The installation is complete when `rei --help` works directly, without
`uv run`. `pipx install reindex` and `python -m pip install reindex`
are also supported. Python 3.12 or newer is required; the Docling dependency
makes the first installation and first PDF scan larger than a typical CLI.

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

Generated text Nodes follow source heading and paragraph boundaries and include
their document position. Table cards include deterministic field statistics and
a real preview. Image cards keep lightweight caption, position, dimensions, and
nearby-source context without an additional vision pass. The installed
`reindex-scan` skill reviews text and related tables once per source document,
keeps descriptions objective, and preserves generated statistics.

For the normal author path, `push` runs the same package check again, so an
explicit `check` is mainly useful after manually editing cards or in CI:

```bash
rei init <collection-dir> --name <name> --agent codex
rei inspect <collection-dir>
rei scan <collection-dir>
rei push <collection-dir> --api-url <api-url>
```

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

### Local embeddings on push

`rei push` automatically uses the locally cached `Qwen/Qwen3-Embedding-0.6B`
model when the optional embedding runtime is installed. It loads the model in
offline mode and uploads vectors with the Collection, so the server does not
need to embed documents. Install the runtime with `pip install 'reindex[embeddings]'`.
Set `REINDEX_LOCAL_EMBEDDINGS=disabled` to skip it, or `qwen` to require it.
On macOS the CLI uses the CPU backend and batches four texts at a time because
MPS can stall on long Qwen inputs. Override with
`REINDEX_LOCAL_EMBEDDING_DEVICE` (`cpu`, `mps`, `cuda`, or `auto`) and
`REINDEX_LOCAL_EMBEDDING_BATCH_SIZE` when appropriate.

`push` finishes local embedding before it opens the server upload session, then
sends a complete target manifest, uploads only missing SHA-256 blobs, and
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

## Python API

The stable Python namespace is `reindex`. It currently exposes the HTTP client
and installed package version; higher-level Collection APIs can grow here
without changing the CLI implementation package.

```python
from reindex import ApiClient, __version__

client = ApiClient("http://127.0.0.1:8000")
print(__version__, client.health())
```

The CLI does not include or provision a hosted API. Remote commands use the
configured ReIndex API; without one, the default is the local development
endpoint at `http://127.0.0.1:8000`.
