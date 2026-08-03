# ReIndex Agent Rules

Read this file before changing the repository.

## Sources of truth

- Treat code as the implementation source of truth, except for the HTTP wire
  contract described below.
- Treat `wiki/reference/reindex-v1.0-standard.md` as the current package protocol.
- Keep `README.md` and `wiki/README.md` as navigation pages.
- Update user or developer guides when their workflows change.

## HTTP contract-first workflow

- Treat `packages/server/src/reindex_server/openapi/reindex-http-v1.yaml` as the
  authoritative HTTP wire contract. FastAPI routes and models implement that
  contract; they do not redefine it.
- Change HTTP APIs in this order: update the OpenAPI contract, update the
  implementation, then update explanatory documentation and clients.
- Preserve existing `/v1` paths, request fields, defaults, response fields,
  status codes, and media types unless the user explicitly authorizes a breaking
  change. Put breaking changes under a new major path such as `/v2`.
- After every HTTP API change, run
  `uv run python scripts/check_http_contract.py` and the relevant API tests. Do
  not finish the task while the contract and FastAPI implementation differ.

## CLI contract-first workflow

- Treat `packages/cli/src/reindex_cli/contract/reindex-cli-v1.yaml` as the
  authoritative CLI interface contract. Command paths, arguments, options,
  defaults, choices, constraints, output protocol, and examples start there.
- Change the CLI in this order: update the contract, update or add a handler,
  compile the Web artifact, then update explanatory documentation. Handlers
  implement behavior and must not register command-line parameters themselves.
- Preserve the current v1 command paths, parameter names, defaults, accepted
  values, JSON response fields, stderr format, and exit codes unless the user
  explicitly authorizes a breaking change.
- After every CLI interface change, run
  `uv run python scripts/compile_cli_contract.py`, then
  `uv run python scripts/compile_cli_contract.py --check` and the relevant CLI
  tests. Do not hand-edit `packages/web-app/public/doc/cli-v1.json`.

## Repository layout

- Keep independently publishable Python packages under `packages/`.
- Keep fixtures, source data, generated ReIndex packages, and fixture builders under `testbase/`.
- Keep active work notes under `tasks/` and reviewed, completed notes under `tasks/history/`.
- Keep every new hand-maintained source or documentation file, and every such
  file materially changed by an agent, at 200 physical lines or fewer. A special
  case may exceed 200 only with a concrete justification in the active task note,
  and must never exceed 300 lines.
- When a file would exceed its limit, split it by responsibility into new files
  or modules while preserving all behavior. Do not evade the limit by deleting
  logic, combining statements, minifying, collapsing readable formatting, moving
  code into strings or data, or otherwise hiding lines.
- Generated lockfiles, vendored assets, generated fixtures, and machine-readable
  contract artifacts are exempt; do not place implementation logic in them or
  hand-edit and compress them merely to reduce their line count.

## Task workflow

- Use `$reindex-task-workflow` for task-note creation, review, completion, reopening, and archival.
- Preserve the user's original request in the task note.
- Never infer human approval from passing tests or finished implementation.
- Archive a task only after a human explicitly approves or marks it complete.
- Before archiving, use the skill's documentation consistency check and update all
  affected README, wiki, guide, example, and task-note content.
- Treat history notes as records, not current product truth.
