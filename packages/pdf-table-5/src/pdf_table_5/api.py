from __future__ import annotations

from pathlib import Path

from .context import Context, Paths
from .io import read_json, sha256
from .page_selection import PageSelection
from .scaffold import initialize_project
from .taskReviewTable import run as review_table
from .workflow import Workflow


def initialize(
    input_pdf: str | Path,
    project: str | Path,
    *,
    force: bool = False,
    pages: PageSelection = None,
) -> dict:
    source, root = Path(input_pdf).resolve(), Path(project).resolve()
    paths = initialize_project(source, root, force=force, pages=pages)
    return read_json(paths.job)


def execute(
    project: str | Path,
    *,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> dict:
    return Workflow(Path(project), model=model, reasoning_effort=reasoning_effort).run()


def verify(project: str | Path) -> dict:
    paths = Paths(Path(project).resolve())
    context = Context(paths)
    job = read_json(paths.job, {})
    source = Path(job.get("demand", {}).get("inputPath", ""))
    if not source.is_file() or job.get("pdfInfo", {}).get("sha256") != sha256(source):
        raise ValueError("Source PDF is missing or differs from job.json")
    listed = read_json(paths.helper_json("listTable.json"), {"tables": []})
    reviews = [review_table(context, item["parseTableId"]) for item in listed["tables"]]
    return {
        "accepted": all(item["accepted"] for item in reviews),
        "tableCount": len(reviews),
        "tables": reviews,
    }
