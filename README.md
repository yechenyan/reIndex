# ReIndex

ReIndex turns local source files into portable, agent-readable knowledge packages.

For Agent-assisted setup, say: “Run `uv tool install --upgrade reindex-cli`, then run `rei init <data-directory> --agent <current-agent>` to install or update ReIndex and its skills.”

## Start here

- Protocol: [`wiki/reference/reindex-v1.0-standard.md`](wiki/reference/reindex-v1.0-standard.md)
- Input manifest: [`wiki/reference/reindex-input-v1.0.md`](wiki/reference/reindex-input-v1.0.md)
- Product overview: [`wiki/overview.md`](wiki/overview.md)
- Quick start: [`wiki/user/quickstart.md`](wiki/user/quickstart.md)
- Architecture: [`wiki/dev/architecture.md`](wiki/dev/architecture.md)
- Development setup: [`wiki/dev/setup.md`](wiki/dev/setup.md)
- Task workflow: [`wiki/dev/tasks.md`](wiki/dev/tasks.md)

## Workspace

- `packages/cli`: `rei`/`reindex` local compiler plus push/pull/search/get client
- `packages/server`: backend service package
- `testbase`: raw fixtures and generated ReIndex packages
- `wiki`: reference, user, and developer documentation
- `tasks`: active and human-approved historical task notes

The first ReIndex 1.0 fixture is under [`testbase/test1/reIndex/test1`](testbase/test1/reIndex/test1/).
The Docling/CSV compiler example and generated package are under
[`testbase/test2`](testbase/test2/).
