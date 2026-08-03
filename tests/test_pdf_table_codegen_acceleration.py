from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest
from PIL import Image, ImageChops

from pdf_table_codegen.artifacts import artifact_hash
from pdf_table_codegen.evidence import _contact, prepare_evidence
from pdf_table_codegen.gates import reopen_inventory, reopen_reference
from pdf_table_codegen.inspection import inspect_inventory
from pdf_table_codegen.inventory import compare_inventories, freeze_inventory
from pdf_table_codegen.job import load_job
from pdf_table_codegen.models import source_sha256
from pdf_table_codegen.reference import freeze_reference
from pdf_table_codegen.workflow import load_state


def _json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _fixture(tmp_path: Path):
    source = tmp_path / "source.pdf"
    document = fitz.open()
    page = document.new_page(width=300, height=200)
    page.draw_rect(fitz.Rect(40, 40, 260, 130))
    page.insert_text((50, 70), "Alpha")
    document.save(source)
    document.close()
    project = tmp_path / "project"
    project.mkdir()
    job_path = project / "job.yaml"
    job_path.write_text(
        """spec: pdf-table-codegen/job@2.0
source: ../source.pdf
extractor: ./extractor.py
evidence_dir: ./evidence
inventory: ./evidence/inventory.frozen.json
reference: ./evidence/visual-reference.json
output_dir: ./output
evidence:
  page_dpi: 96
""",
        encoding="utf-8",
    )
    return load_job(job_path), project


def _draft(job, role: str, bbox=None):
    return {
        "spec": "pdf-table-codegen/inventory-draft@2.0",
        "role": role,
        "independent_visual_review": True,
        "source_sha256": source_sha256(job.source),
        "scope": "full_document",
        "tables": [{
            "id": "example", "title": "Example", "pages": [1],
            "segments": [{"page": 1, "bbox": bbox or [40, 40, 260, 130], "data_rows": [1, 1]}],
        }],
        "excluded_regions": [],
    }


def _compare(job, tmp_path, conflict=False):
    execution, qa = tmp_path / "execution.json", tmp_path / "qa.json"
    _json(execution, _draft(job, "execution_agent"))
    _json(qa, _draft(job, "qa_agent", [40, 45, 260, 130] if conflict else None))
    return compare_inventories(job, execution, qa)


def _reconciliation(job, tmp_path, decisions=None, bbox=None):
    path = tmp_path / "reconciliation.json"
    body = {
        "spec": "pdf-table-codegen/inventory-reconciliation@2.0",
        "role": "main_agent",
        "source_sha256": source_sha256(job.source),
        "inventory_diff_sha256": artifact_hash(job.inventory_diff),
        "scope": "full_document",
        "tables": _draft(job, "execution_agent", bbox)["tables"],
        "excluded_regions": [],
        "decisions": decisions or [],
    }
    _json(path, body)
    return path


def test_main_agent_must_resolve_every_inventory_conflict(tmp_path: Path) -> None:
    job, _ = _fixture(tmp_path)
    prepare_evidence(job)
    report = _compare(job, tmp_path, conflict=True)
    assert report["summary"] == {"matches": 0, "conflicts": 1}
    with pytest.raises(ValueError, match="requires phase 'prepared'"):
        _compare(job, tmp_path, conflict=True)
    with pytest.raises(ValueError, match="every inventory conflict"):
        freeze_inventory(job, _reconciliation(job, tmp_path))
    resolution = [40, 40, 260, 130]
    decisions = [{
        "path": "tables.example.segments",
        "resolution": [{"page": 1, "bbox": resolution, "data_rows": [1, 1]}],
        "reason": "full-resolution page confirms the upper border",
        "evidence_pages": [1],
    }]
    frozen = freeze_inventory(job, _reconciliation(job, tmp_path, decisions, resolution))
    assert frozen["decisions"] == decisions


def test_inventory_bbox_must_stay_inside_page(tmp_path: Path) -> None:
    job, _ = _fixture(tmp_path)
    prepare_evidence(job)
    execution, qa = tmp_path / "execution.json", tmp_path / "qa.json"
    _json(execution, _draft(job, "execution_agent", [40, 40, 400, 130]))
    _json(qa, _draft(job, "qa_agent"))
    with pytest.raises(ValueError, match="outside page"):
        compare_inventories(job, execution, qa)


def test_reference_requires_qa_role_and_string_cells(tmp_path: Path) -> None:
    job, project = _fixture(tmp_path)
    prepare_evidence(job)
    _compare(job, tmp_path)
    freeze_inventory(job, _reconciliation(job, tmp_path))
    inspect_inventory(job)
    draft = {
        "spec": "pdf-table-codegen/reference-draft@2.0",
        "role": "execution_agent",
        "independent_from_extractor": True,
        "source_evidence_only": True,
        "source_sha256": source_sha256(job.source),
        "inventory_sha256": artifact_hash(job.inventory),
        "tables": [{
            "id": "example", "column_count": 1, "row_count": 1,
            "header": ["Name"], "samples": [{"row_index": 0, "values": [None]}],
        }],
    }
    path = tmp_path / "reference.json"
    _json(path, draft)
    with pytest.raises(ValueError, match="QA agent"):
        freeze_reference(job, path)
    draft["role"] = "qa_agent"
    draft["tables"][0]["samples"][0] = {
        "row_index": 0, "source_values": ["Alpha"], "normalized_values": ["Alpha"]
    }
    _json(path, draft)
    assert freeze_reference(job, path)["tables"][0]["samples"][0]["values"] == ["Alpha"]
    reopen_reference(job, "test alternate QA sample representation")
    draft["tables"][0]["samples"][0] = {"row_index": 0, "values": [None]}
    _json(path, draft)
    with pytest.raises(ValueError, match="must be strings"):
        freeze_reference(job, path)
    assert not (project / "evidence" / "visual-reference.json").exists()


def test_reopen_invalidates_downstream_artifacts(tmp_path: Path) -> None:
    job, project = _fixture(tmp_path)
    prepare_evidence(job)
    _compare(job, tmp_path)
    freeze_inventory(job, _reconciliation(job, tmp_path))
    inspect_inventory(job)
    reference = tmp_path / "reference.json"
    _json(reference, {
        "spec": "pdf-table-codegen/reference-draft@2.0", "role": "qa_agent",
        "independent_from_extractor": True, "source_evidence_only": True,
        "source_sha256": source_sha256(job.source),
        "inventory_sha256": artifact_hash(job.inventory),
        "tables": [{"id": "example", "column_count": 1, "row_count": 1,
                    "header": ["Name"], "samples": [{"row_index": 0, "values": ["Alpha"]}]}],
    })
    freeze_reference(job, reference)
    assert reopen_reference(job, "QA typo")["phase"] == "inspected"
    assert not job.reference.exists()
    assert reopen_inventory(job, "missed table")["phase"] == "prepared"
    assert not job.inventory.exists()
    assert not (project / "evidence" / "tables").exists()


def test_prepare_cache_and_later_contact_layout(tmp_path: Path) -> None:
    job, _ = _fixture(tmp_path)
    assert prepare_evidence(job)["cache_hit"] is False
    assert prepare_evidence(job)["cache_hit"] is True
    pages = []
    for page_number in range(13, 18):
        path = tmp_path / f"page-{page_number}.png"
        image = Image.new("RGB", (120, 160), "white")
        image.putpixel((page_number, page_number), (0, 0, 0))
        image.save(path)
        pages.append((page_number, path))
    target = tmp_path / "contact.jpg"
    _contact(pages, target)
    with Image.open(target) as contact:
        white = Image.new("RGB", contact.size, "white")
        assert ImageChops.difference(contact.convert("RGB"), white).getbbox() is not None
    assert load_state(job.evidence_dir)["phase"] == "prepared"
