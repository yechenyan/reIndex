# Development setup

## Prerequisites

- Python 3.12
- uv
- Git

## Install and verify

```bash
uv sync
uv run pytest
uv run reindex doctor
```

Build an individual distribution with:

```bash
uv build --package reindex-cli
uv build --package reindex-server
```

Package metadata and dependency ranges live in each package's `pyproject.toml`.
The root `pyproject.toml` only defines workspace and development dependencies.

