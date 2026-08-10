from __future__ import annotations

from pathlib import Path

from .context import Paths
from .io import read_json, write_json
from .page_selection import PageSelection, normalize_pages
from .pdf import inspect_pdf, sheet_shape
from .state import initial_state, utc_now


MAIN_TEMPLATE = '''from pathlib import Path

from pdf_table_5 import execute as _execute
from pdf_table_5 import verify as _verify

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def execute(*, model: str | None = None, reasoning_effort: str | None = None) -> dict:
    """Extract every discovered target table, resuming an interrupted run."""
    return _execute(PROJECT_ROOT, model=model, reasoning_effort=reasoning_effort)


def verify() -> dict:
    """Recheck generated CSV files and recorded samples without running agents."""
    return _verify(PROJECT_ROOT)
'''

SCREENSHOT_TEMPLATE = '''#!/usr/bin/env python3
from pdf_table_5.screenshot import main

if __name__ == "__main__":
    raise SystemExit(main())
'''

RUNTIME_AGENT_GUIDANCE = '''# PDF Table Runtime Workspace

This directory is generated extraction data, not repository implementation work.
The active agent prompt already contains the required contracts and file contents.
Use its inline evidence and attached table crops as the normal path, returning structured output directly.
Use the exact supplied paths and scratch directory only when source diagnosis or visual rechecking is needed.
Repository discovery, workflow skills, task notes, and edits outside the supplied scratch area do not help extraction.
'''

def initialize_project(
    input_pdf: Path,
    project: Path,
    *,
    force: bool = False,
    pages: PageSelection = None,
) -> Paths:
    input_pdf, project = input_pdf.resolve(), project.resolve()
    if not input_pdf.is_file():
        raise FileNotFoundError(input_pdf)
    paths = Paths(project)
    for directory in (paths.helper, paths.tables, paths.strategy, paths.report, paths.output):
        directory.mkdir(parents=True, exist_ok=True)
    guidance = project / "AGENTS.md"
    if not guidance.exists():
        guidance.write_text(RUNTIME_AGENT_GUIDANCE, encoding="utf-8")
    if paths.job.exists() and not force:
        existing = read_json(paths.job, {})
        recorded = Path(existing.get("demand", {}).get("inputPath", "")).resolve()
        if recorded != input_pdf:
            raise ValueError(f"Project already belongs to another PDF: {recorded}")
        total_pages = int(existing.get("pdfInfo", {}).get("totalPages", 0))
        requested = normalize_pages(pages, total_pages)
        current = existing.get("demand", {}).get("targetPages")
        if requested != current:
            raise ValueError(f"Project page selection is {current}; requested {requested}")
        return paths
    pdf_info = inspect_pdf(input_pdf, pages)
    target_pages = normalize_pages(pages, pdf_info["totalPages"])
    demand = {"inputPath": str(input_pdf), "outputPath": str(paths.output)}
    if target_pages is not None:
        demand["targetPages"] = target_pages
    job = {
        "version": "pdf-table-5/job@1.0",
        "createdAt": utc_now(),
        "demand": demand,
        "pdfInfo": {key: value for key, value in pdf_info.items() if key != "pages"},
        "aggregateImages": sheet_shape(len(pdf_info["pages"])),
    }
    params = {
        "version": "pdf-table-5/parameters@1.0",
        "overviewDpi": 96,
        "finderDetailDpi": 180,
        "mergeDpi": 180,
        "tableDpi": 216,
        "bboxMarginPt": 72,
        "maxRepairAttempts": 3,
        "agentModel": "gpt-5.6-terra",
        "agentReasoningEffort": "medium",
    }
    write_json(paths.job, job)
    write_json(paths.params, params)
    write_json(paths.states, initial_state())
    paths.steps.touch(exist_ok=True)
    write_json(paths.helper / "finalTable.json", {"version": "pdf-table-5/final-table@1.0", "tables": []})
    (paths.parse / "main.py").write_text(MAIN_TEMPLATE, encoding="utf-8")
    (paths.helper / "screenshot.py").write_text(SCREENSHOT_TEMPLATE, encoding="utf-8")
    (paths.strategy / "__init__.py").touch(exist_ok=True)
    return paths
