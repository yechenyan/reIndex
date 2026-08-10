---
name: pdf-to-markdown
description: Convert one local PDF to verified Markdown with ReIndex LiteParse extraction, table sampling, and pdf-table-5 fallback.
---

# PDF to Markdown

Treat the PDF path supplied with this skill as the only required input. Use the existing ReIndex converter;
do not reimplement extraction or use another local PDF-to-Markdown product.

## Execute

1. Resolve the input to an absolute path and require an existing `.pdf` file.
2. Use the ReIndex repository four parent directories above this `SKILL.md` as the working directory.
3. Unless the user specifies an output location, create `<pdf-stem>-pdf-to-markdown-run` next to the PDF.
4. Run with absolute, shell-quoted paths:

```bash
uv run --package pdf-to-markdown pdf-to-markdown \
  "/absolute/path/input.pdf" \
  --output "/absolute/path/<pdf-stem>-pdf-to-markdown-run/output.md" \
  --project "/absolute/path/<pdf-stem>-pdf-to-markdown-run/work"
```

Do not set model, reasoning effort, or workers unless requested. Wait for the full process; specialist table
parsing can take several minutes. Reuse the same project directory when rerunning the same input.

## Verify

Report success only when the command exits with status 0, `output.md` exists, and `work/report.json` has:

- `accepted: true`
- an empty `failedTableIds`
- an empty `unmatchedSpecialistTables`
- an empty `failedSpecialistTables`

When `specialistPages` is non-empty, also report `specialistPlacements`; it records which accepted
`pdf-table-5` tables were written to each page group and which LiteParse fragments they replaced.

Report the absolute output and report paths, `durationMs`, `statusCounts`, `specialistPages`, and any
`specialistPlacements`. On failure, preserve all run artifacts, report the exact error, and still report the
best-effort `output.md` and `accepted: false` report when they exist. Do not silently claim fallback content is
verified or edit the converter.
