from __future__ import annotations

from pathlib import Path
from typing import Any

from .engine import execute_project
from .paths import ProjectPaths
from .scaffold import initialize_project
from .verify import verify_project


def initialize(input_pdf: str | Path, project_root: str | Path) -> dict[str, Any]:
    paths = initialize_project(Path(input_pdf), Path(project_root))
    return {"projectRoot": str(paths.root), "job": str(paths.job), "params": str(paths.params)}


def execute(project_root: str | Path) -> dict[str, Any]:
    return execute_project(ProjectPaths(Path(project_root).expanduser().resolve()))


def verify(project_root: str | Path) -> dict[str, Any]:
    return verify_project(ProjectPaths(Path(project_root).expanduser().resolve()))
