from __future__ import annotations

from pathlib import Path

from .workflow import Workflow


def convert(
    input_pdf: str | Path,
    output_markdown: str | Path,
    *,
    project: str | Path | None = None,
    model: str = "gpt-5.6-terra",
    reasoning_effort: str = "medium",
    workers: int | None = None,
) -> dict:
    source = Path(input_pdf)
    output = Path(output_markdown)
    workspace = Path(project) if project is not None else output.with_suffix(output.suffix + ".work")
    return Workflow(
        source,
        output,
        workspace,
        model=model,
        reasoning_effort=reasoning_effort,
        workers=workers,
    ).run()
