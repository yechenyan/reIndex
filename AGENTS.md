# ReIndex Agent Rules

Read this file before changing the repository.

## Sources of truth

- Treat code as the implementation source of truth.
- Treat `wiki/reference/reindex-v1.0-standard.md` as the current package protocol.
- Keep `README.md` and `wiki/README.md` as navigation pages.
- Update user or developer guides when their workflows change.

## Repository layout

- Keep independently publishable Python packages under `packages/`.
- Keep fixtures, source data, generated ReIndex packages, and fixture builders under `testbase/`.
- Keep active work notes under `tasks/` and reviewed, completed notes under `tasks/history/`.
- Prefer maintained code and documentation at 200 lines or fewer. Split them
  before 300 lines; generated fixtures are exempt when their size follows source data.

## Task workflow

- Use `$reindex-task-workflow` for task-note creation, review, completion, reopening, and archival.
- Preserve the user's original request in the task note.
- Never infer human approval from passing tests or finished implementation.
- Archive a task only after a human explicitly approves or marks it complete.
- Before archiving, use the skill's documentation consistency check and update all
  affected README, wiki, guide, example, and task-note content.
- Treat history notes as records, not current product truth.
