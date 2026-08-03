from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

from pdf_table_codegen.artifacts import artifact_hash
from pdf_table_codegen.evidence import prepare_evidence
from pdf_table_codegen.gates import finalize_job
from pdf_table_codegen.inspection import inspect_inventory
from pdf_table_codegen.inventory import compare_inventories, freeze_inventory
from pdf_table_codegen.job import load_job
from pdf_table_codegen.models import source_sha256
from pdf_table_codegen.reference import freeze_reference, sample_indices
from pdf_table_codegen.runner import _module, run_job, verify_job
from pdf_table_codegen.skill import install_skill
from pdf_table_codegen.workflow import load_state


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _project(tmp_path: Path):
    source = tmp_path / "source.pdf"
    document = fitz.open()
    page = document.new_page(width=300, height=200)
    page.draw_rect(fitz.Rect(40, 40, 260, 130))
    page.draw_line((150, 40), (150, 130))
    page.draw_line((40, 80), (260, 80))
    page.insert_text((50, 65), "Name")
    page.insert_text((160, 65), "Value")
    page.insert_text((50, 105), "Alpha")
    page.insert_text((160, 105), "1")
    document.save(source)
    document.close()
    project = tmp_path / "project"
    project.mkdir()
    job_path = project / "job.yaml"
    job_path.write_text(
        """spec: pdf-table-codegen/job@2.0
name: workflow-test
source: ../source.pdf
extractor: ./extractor.py
evidence_dir: ./evidence
inventory: ./evidence/inventory.frozen.json
reference: ./evidence/visual-reference.json
output_dir: ./output
evidence:
  page_dpi: 96
  table_dpi: 144
policy:
  compatibility: exact
""",
        encoding="utf-8",
    )
    return load_job(job_path), project


def _inventory(job, role: str) -> dict:
    return {
        "spec": "pdf-table-codegen/inventory-draft@2.0",
        "role": role,
        "independent_visual_review": True,
        "source_sha256": source_sha256(job.source),
        "scope": "full_document",
        "tables": [{
            "id": "example",
            "title": "Example",
            "pages": [1],
            "segments": [{"page": 1, "bbox": [40, 40, 260, 130], "data_rows": [1, 1]}],
        }],
        "excluded_regions": [],
    }


def _freeze_inventory(job, tmp_path: Path) -> None:
    execution, qa = tmp_path / "execution.json", tmp_path / "qa.json"
    _write(execution, _inventory(job, "execution_agent"))
    _write(qa, _inventory(job, "qa_agent"))
    compare_inventories(job, execution, qa)
    reconciliation = tmp_path / "reconciliation.json"
    _write(reconciliation, {
        "spec": "pdf-table-codegen/inventory-reconciliation@2.0",
        "role": "main_agent",
        "source_sha256": source_sha256(job.source),
        "inventory_diff_sha256": artifact_hash(job.inventory_diff),
        "scope": "full_document",
        "tables": _inventory(job, "execution_agent")["tables"],
        "excluded_regions": [],
        "decisions": [],
    })
    freeze_inventory(job, reconciliation)
    inspect_inventory(job)


def _extractor(job) -> str:
    digest = source_sha256(job.source)
    return f'''from pathlib import Path
from pdf_table_codegen import *
HASH = "{digest}"
def can_handle(source: Path):
    actual = source_sha256(source)
    return CompatibilityReport(actual == HASH, "exact hash", actual)
def extract_tables(request):
    table = ExtractedTable("example", "Example", ["Name", "Value"], [["Alpha", "1"]], [1], [RowProvenance(1, (40, 80, 260, 130), "page-1")])
    return ExtractionResult("example", "1.0.0", HASH, [table])
'''


def _freeze_reference(job, tmp_path: Path) -> None:
    draft = tmp_path / "reference.json"
    _write(draft, {
        "spec": "pdf-table-codegen/reference-draft@2.0",
        "role": "qa_agent",
        "independent_from_extractor": True,
        "source_evidence_only": True,
        "source_sha256": source_sha256(job.source),
        "inventory_sha256": artifact_hash(job.inventory),
        "tables": [{
            "id": "example", "column_count": 2, "row_count": 1,
            "header": ["Name", "Value"],
            "samples": [{"row_index": 0, "values": ["Alpha", "1"]}],
        }],
    })
    freeze_reference(job, draft)


def test_seven_stage_workflow_reaches_machine_complete(tmp_path: Path) -> None:
    job, project = _project(tmp_path)
    assert prepare_evidence(job)["cache_hit"] is False
    _freeze_inventory(job, tmp_path)
    job.extractor.write_text(_extractor(job), encoding="utf-8")
    _freeze_reference(job, tmp_path)
    assert run_job(job.path).tables[0].rows == [["Alpha", "1"]]
    report = verify_job(job.path)
    assert report["ok"]
    assert {item["name"] for item in report["checks"]} >= {
        "deterministic_double_run", "full_table_inventory", "inventory_sha256"
    }
    review = tmp_path / "final-review.json"
    _write(review, {
        "spec": "pdf-table-codegen/final-review@2.0",
        "role": "main_agent",
        "verification_sha256": artifact_hash(project / "output" / "verification.json"),
        "verdict": "machine_complete",
        "checklist": {
            "inventory_conflicts_resolved": True,
            "all_expected_tables_present": True,
            "qa_reference_passed": True,
            "runtime_qa_passed": True,
            "deterministic_outputs": True,
            "output_files_complete": True,
        },
        "unresolved_warnings": [],
    })
    original = job.extractor.read_text(encoding="utf-8")
    job.extractor.write_text(original + "\n# changed after verify\n", encoding="utf-8")
    with pytest.raises(ValueError, match="verified inputs changed"):
        finalize_job(job, review)
    job.extractor.write_text(original, encoding="utf-8")
    finalized = finalize_job(job, review)
    assert finalized["workflow"]["phase"] == "machine_complete"
    assert finalized["review"]["status"] == "machine_complete_not_human_approved"


def test_reference_sampling_handles_short_tables() -> None:
    assert [sample_indices(value) for value in range(6)] == [
        [], [0], [0, 1], [0, 1, 2], [0, 1, 2, 3], [0, 1, 3, 4]
    ]


def test_loading_extractor_does_not_write_bytecode(tmp_path: Path) -> None:
    extractor = tmp_path / "extractor.py"
    extractor.write_text("VALUE = 1\n", encoding="utf-8")
    assert _module(extractor).VALUE == 1
    assert not (tmp_path / "__pycache__").exists()


def test_skill_installs_idempotently(tmp_path: Path) -> None:
    target, status = install_skill(tmp_path)
    assert status == "installed"
    assert (target / "SKILL.md").is_file()
    assert install_skill(tmp_path) == (target, "unchanged")


def test_run_is_blocked_before_qa_reference(tmp_path: Path) -> None:
    job, _ = _project(tmp_path)
    prepare_evidence(job)
    _freeze_inventory(job, tmp_path)
    job.extractor.write_text(_extractor(job), encoding="utf-8")
    with pytest.raises(ValueError, match="reference_frozen"):
        run_job(job.path)
    assert load_state(job.evidence_dir)["phase"] == "inspected"
