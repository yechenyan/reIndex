from __future__ import annotations

import os
from pathlib import Path

from pdf_extractor_pdf.models import source_sha256
from pdf_extractor_pdf.workflow import update_phase

JOB_TEMPLATE = """spec: pdf-extractor-pdf/job@1.0
source: {source}
main: ./main.py
evidence_dir: ./evidence
inventory: ./evidence/inventory.json
reference: ./evidence/reference.json
output_dir: ../output
request: {request}
evidence:
  thumbnail_dpi: 72
  contact_columns: 4
  contact_pages: 8
  contact_overlap_pages: 1
  finder_candidate_dpi: 150
  table_dpi: 220
policy:
  scope: full_document
  extractor_timeout_seconds: 120
  require_row_bbox: true
  merge_candidate_threshold: 0.85
  require_independent_agents: true
  require_parallel_extraction_qa: true
"""

MAIN_TEMPLATE = '''"""PDF-specific extractor. Keep source-specific rules in this directory."""
from pathlib import Path

from pdf_extractor_pdf import (
    ExtractedTable,
    ExtractionResult,
    RowProvenance,
    project_entry,
    source_sha256,
)


def extract(source: Path, inventory: dict) -> ExtractionResult:
    """Return all frozen logical tables; implement after inventory inspection."""
    raise NotImplementedError("write source-specific extraction rules")


if __name__ == "__main__":
    project_entry(extract)
'''


def initialize_project(project_dir: Path, source: Path, request: str, force: bool = False) -> Path:
    project_dir, source = project_dir.resolve(), source.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    extractor = project_dir / "extractor"
    evidence = extractor / "evidence"
    output = project_dir / "output"
    extractor.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    job = extractor / "job.yaml"
    main = extractor / "main.py"
    if (job.exists() or main.exists()) and not force:
        raise FileExistsError("extractor/job.yaml or extractor/main.py already exists")
    relative = Path(os.path.relpath(source, extractor)).as_posix()
    job.write_text(JOB_TEMPLATE.format(source=relative, request=_yaml_string(request)), encoding="utf-8")
    main.write_text(MAIN_TEMPLATE, encoding="utf-8")
    update_phase(evidence, "initialized", "project_initialized", {"source_sha256": source_sha256(source)})
    return job


def _yaml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'
