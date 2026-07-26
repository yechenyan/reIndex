# Quick start

Requires Python 3.12 and uv.

```bash
uv sync
uv run reindex doctor
uv run reindex-server run
```

The API health endpoint is `http://127.0.0.1:8000/health`.

To rebuild the first PDF fixture:

```bash
uv run --package reindex-cli python testbase/test1/build_reindex.py
```

The command reads `testbase/test1/raw/` and replaces only the generated
`testbase/test1/reIndex/` package.

