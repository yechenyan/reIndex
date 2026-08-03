from __future__ import annotations

import json
from pathlib import Path

import fitz

from pdf_table_codegen.evidence import prepare_evidence
from pdf_table_codegen.freezing import freeze_inventory, freeze_reference
from pdf_table_codegen.inspection import inspect_inventory
from pdf_table_codegen.job import load_job
from pdf_table_codegen.scaffold import build_assertion_hints


def _json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _fixture(tmp_path: Path):
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
        """spec: pdf-table-codegen/job@1.0
name: acceleration-test
source: ../source.pdf
extractor: ./extractor.py
evidence_dir: ./evidence
inventory: ./evidence/inventory.frozen.json
reference: ./evidence/visual-reference.json
output_dir: ./output
evidence:
  page_dpi: 96
  table_dpi: 144
  contact_pages: 12
""",
        encoding="utf-8",
    )
    return load_job(job_path), project


def test_safe_acceleration_workflow(tmp_path: Path) -> None:
    job, project = _fixture(tmp_path)
    assert prepare_evidence(job)["cache_hit"] is False
    assert prepare_evidence(job)["cache_hit"] is True

    inventory_draft = tmp_path / "inventory.json"
    _json(inventory_draft, {
        "scope": "full_document",
        "tables": [{
            "id": "example",
            "caption": "Example",
            "pages": [1],
            "segments": [{"page": 1, "bbox": [40, 40, 260, 130], "data_rows": [1, 1]}],
        }],
        "explicit_exclusions": [],
    })
    inventory = freeze_inventory(job, inventory_draft)
    assert inventory["status"] == "frozen"
    pack = inspect_inventory(job)
    assert len(pack["segments"]) == 1
    table_dir = project / "evidence" / "tables" / "example"
    assert len(list(table_dir.glob("*.png"))) == 1
    geometry = json.loads(next(table_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert geometry["word_count"] == 4
    assert geometry["drawing_lines"]

    reference_draft = tmp_path / "reference.json"
    _json(reference_draft, {
        "audit_method": "independent visual inspection",
        "tables": [{
            "id": "example",
            "title": "Example",
            "pages": [1],
            "column_count": 2,
            "row_count": 1,
            "header": ["Name", "Value"],
            "samples": [{"row_index": 0, "values": ["Alpha", "1"]}],
        }],
    })
    reference = freeze_reference(job, reference_draft)
    assert reference["inventory_sha256"]
    hints = build_assertion_hints(job)
    assert hints["table_order"] == ["example"]
    assert hints["tables"][0]["required_shape"] == [1, 2]


def test_prepare_cache_rebuilds_tampered_evidence(tmp_path: Path) -> None:
    job, _ = _fixture(tmp_path)
    prepare_evidence(job)
    page = job.evidence_dir / "pages" / "page-0001.png"
    page.write_bytes(b"tampered")
    assert prepare_evidence(job)["cache_hit"] is False
    assert page.stat().st_size > len(b"tampered")
