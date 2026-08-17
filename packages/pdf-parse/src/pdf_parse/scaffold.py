from __future__ import annotations

from pathlib import Path

from .constants import (
    DEFAULT_DPI,
    DEFAULT_MODEL,
    DEFAULT_REASONING,
    FORMAT_VERSION,
    MAX_DPI,
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_SIDE,
    MAX_REPAIRS,
    MIN_DPI,
)
from .io_utils import atomic_json, sha256_file, utc_now
from .paths import ProjectPaths
from .state import initial_state


MAIN_TEMPLATE = '''from pathlib import Path
from pdf_parse.project_api import execute as _execute, verify as _verify

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def execute():
    return _execute(PROJECT_ROOT)


def verify():
    return _verify(PROJECT_ROOT)


if __name__ == "__main__":
    print(execute())
'''


def initialize_project(
    input_pdf: Path,
    project_root: Path,
    output_path: Path | None = None,
) -> ProjectPaths:
    source = input_pdf.expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".pdf":
        raise ValueError(f"Readable PDF required: {source}")
    paths = ProjectPaths(project_root.expanduser().resolve())
    paths.create_directories()
    digest = sha256_file(source)
    job = {
        "formatVersion": FORMAT_VERSION,
        "createdAt": utc_now(),
        "demand": {
            "inputPath": str(source),
            "outputPath": str((output_path or paths.output).resolve()),
        },
        "pdfInfo": {
            "isValidPdf": True,
            "sha256": digest,
            "sizeBytes": source.stat().st_size,
        },
        "coordinateSystem": {
            "name": "liteparse-viewport",
            "origin": "top-left",
            "xDirection": "right",
            "yDirection": "down",
            "unit": "pt",
            "dpi": 72,
            "pageNumbering": "1-based",
        },
    }
    params = {
        "formatVersion": FORMAT_VERSION,
        "liteParse": {"version": "2.13.0", "ocrEnabled": False},
        "screenshots": {
            "defaultDpi": DEFAULT_DPI,
            "minDpi": MIN_DPI,
            "maxDpi": MAX_DPI,
            "maxImageSide": MAX_IMAGE_SIDE,
            "maxImagePixels": MAX_IMAGE_PIXELS,
        },
        "agents": {
            "model": DEFAULT_MODEL,
            "reasoningEffort": DEFAULT_REASONING,
            "maxRepairsPerTable": MAX_REPAIRS,
        },
    }
    atomic_json(paths.job, job)
    atomic_json(paths.params, params)
    if not paths.states.exists():
        atomic_json(paths.states, initial_state(digest))
    main_path = paths.parse / "main.py"
    if not main_path.exists():
        main_path.write_text(MAIN_TEMPLATE, encoding="utf-8")
    return paths
