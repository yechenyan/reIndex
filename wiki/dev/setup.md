# Development setup

## Prerequisites

- Python 3.12
- uv
- Git

## Install and verify

```bash
uv sync
uv run pytest
uv run rei --help
uv run rei init testbase/test2 --name test2 --agent codex
uv run rei inspect testbase/test2
uv run rei check testbase/test2
```

真实 ParadeDB 与 HTTP E2E 的启动、执行和清理步骤见
[`testing.md`](testing.md)。

Build an individual distribution with:

```bash
uv build --package reindex-cli
uv build --package reindex-server
```

Package metadata and dependency ranges live in each package's `pyproject.toml`.
The root `pyproject.toml` only defines workspace and development dependencies.
