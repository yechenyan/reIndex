---
name: reindex-task-workflow
description: Manage ReIndex project task notes from intake through implementation, documentation consistency review, human approval, archival, and reopening. Use for any task performed in the ReIndex repository that creates or updates a note under tasks/, records validation or decisions, marks work ready for review, responds to human approval, checks documentation before completion, moves completed work into tasks/history/, or reopens historical work.
---

# ReIndex Task Workflow

Keep task records useful without treating implementation success as approval.

## Start a task

1. Read `AGENTS.md` and the relevant reference, user, and developer docs.
2. Find the matching active note under `tasks/`.
3. If none exists, create a concise, uniquely named Markdown note under `tasks/`.
4. Preserve the user's original request verbatim or as a clearly labeled quotation.
5. Record scope, assumptions, and acceptance checks separately from the request.

Never place active work directly in `tasks/history/`.

## Implement and prepare review

1. Update code and current documentation.
2. Record important decisions and deviations in the active note.
3. Run checks proportional to the change.
4. Add a concise implementation summary and exact validation commands or results.
5. Set the note status to `等待人工审核`.

Passing tests, committing code, or an agent saying the work is finished does not
complete the task. Keep the note in `tasks/` until a human explicitly approves it
or says it is complete.

## Check documentation before completion

Before setting a task to `已完成` or moving it into `tasks/history/`:

1. Identify every behavior, schema, command, path, example, deployment setting,
   and workflow changed by the task.
2. Search `README.md`, `wiki/`, package and fixture READMEs, generated examples,
   and the active task note for stale names, paths, numbering, counts, or claims.
3. Update every affected current document. Preserve obsolete details only when
   they are clearly labeled as historical context or negative regression checks.
4. Run documentation links, examples, generators, tests, or other relevant checks
   again after the edits.
5. Record the documentation audit and validation evidence in the active task note.
   If no document needed a change, record what was checked and why it remains
   accurate.

Do not archive while current documentation contradicts the implementation.

## Archive approved work

After explicit human approval:

1. Complete the documentation check above.
2. Record who approved the work and the approval context available in the task.
3. Set the status to `已完成`.
4. Confirm the note contains the request, outcome, decisions, documentation audit,
   and validation.
5. Move the note, without duplicating it, to `tasks/history/`.
6. Keep current behavior documented in code and `wiki/`; history is not canonical.

Do not rewrite the original request while archiving.

## Reopen work

When a human reopens or materially extends an archived task:

1. Move the note from `tasks/history/` back to `tasks/`.
2. Set the status to `进行中`.
3. Append the new request and keep the previous completion record intact.
4. Repeat implementation, review, and approval; never assume the previous approval
   covers new scope.
