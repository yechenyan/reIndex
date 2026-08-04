from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

from pdf_extractor_pdf.artifacts import write_json
from pdf_extractor_pdf.evidence import prepare
from pdf_extractor_pdf.inventory import freeze_inventory
from pdf_extractor_pdf.job import load_job
from pdf_extractor_pdf.metrics import record_agent
from pdf_extractor_pdf.models import source_sha256
from pdf_extractor_pdf.scaffold import initialize_project
from pdf_extractor_pdf.skill import install_skill


def _job(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = project / "input.pdf"
    document = fitz.open()
    document.new_page(width=200, height=100).insert_text((20, 30), "no table")
    document.save(source)
    document.close()
    return load_job(initialize_project(project, source, "Extract tables")), project


def test_scaffold_keeps_every_non_output_artifact_in_extractor(tmp_path: Path) -> None:
    job, project = _job(tmp_path)
    assert job.path == project / "extractor" / "job.yaml"
    assert job.main == project / "extractor" / "main.py"
    assert job.evidence_dir == project / "extractor" / "evidence"
    assert job.output_dir == project / "output"


def test_inventory_requires_exact_page_coverage(tmp_path: Path) -> None:
    job, _ = _job(tmp_path)
    prepare(job)
    draft = job.evidence_dir / "draft.json"
    write_json(draft, {
        "spec": "pdf-extractor-pdf/inventory-draft@1.0", "role": "finder_agent",
        "reviewed_all_pages": True, "source_sha256": source_sha256(job.source),
        "page_findings": [], "tables": [{
            "id": "x", "title": "x", "segments": [{"id": "s1", "page": 1, "bbox": [1, 1, 10, 10]}],
        }],
    })
    with pytest.raises(ValueError, match="every page exactly once"):
        freeze_inventory(job, draft)


def test_agent_metric_preserves_unavailable_token_usage(tmp_path: Path) -> None:
    job, _ = _job(tmp_path)
    path = record_agent(job.evidence_dir, {
        "role": "finder_agent", "model": "gpt-5.6-terra",
        "started_at": "2026-08-04T00:00:00Z", "ended_at": "2026-08-04T00:01:00Z",
        "conversation_turns": 1, "token_usage": None,
    })
    value = json.loads(path.read_text().splitlines()[0])
    assert value["token_usage"] is None


def test_skill_installs_idempotently(tmp_path: Path) -> None:
    target, status = install_skill(tmp_path)
    assert status == "installed" and (target / "SKILL.md").is_file()
    assert install_skill(tmp_path) == (target, "unchanged")
