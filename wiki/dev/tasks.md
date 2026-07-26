# Task workflow

Every implementation task has one Markdown note under `tasks/`. Keep the user's
original request, assumptions, decisions, implementation summary, and validation
evidence in that note.

Passing tests means a task is ready for review, not complete. Keep its note active
until a human explicitly approves it or says it is complete. After approval:

1. audit README, wiki, guides, examples, and the task note for stale behavior,
   paths, numbering, counts, or commands;
2. update every affected current document and rerun relevant checks;
3. record the approval, documentation audit, validation, and final outcome;
4. move the note to `tasks/history/`;
5. leave current behavior in code and reference documentation, not in history.

If the audit finds that no documentation change is needed, record what was checked
and why it remains accurate. Never archive a task while current documentation
contradicts the implementation.

If a completed task is reopened, move the note back to `tasks/` before changing
the implementation. The repository skill
`.agents/skills/reindex-task-workflow/SKILL.md` contains the agent procedure.
