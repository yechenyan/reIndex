from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

from pdf_extractor_pdf.artifacts import artifact_hash, read_json, write_json
from pdf_extractor_pdf.cache import verify_cache
from pdf_extractor_pdf.evidence import prepare
from pdf_extractor_pdf.gates import finalize
from pdf_extractor_pdf.inspection import inspect_inventory
from pdf_extractor_pdf.inventory import freeze_inventory
from pdf_extractor_pdf.inventory_audit import audit_inventory
from pdf_extractor_pdf.job import load_job
from pdf_extractor_pdf.models import source_sha256
from pdf_extractor_pdf.metrics import finish_stage, start_stage
from pdf_extractor_pdf.reference import freeze_reference, required_sample_indices
from pdf_extractor_pdf.runner import execute
from pdf_extractor_pdf.scaffold import initialize_project
from pdf_extractor_pdf.validation import check_existing, validate
from pdf_extractor_pdf.workflow import load_state


def _fixture(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = project / "source.pdf"
    document = fitz.open()
    for suffix in ["A", "B"]:
        page = document.new_page(width=300, height=200)
        page.draw_rect(fitz.Rect(30, 40, 270, 150))
        page.insert_text((40, 65), f"Name Value {suffix}")
    document.save(source)
    document.close()
    job_path = initialize_project(project, source, "Extract the continued table")
    job_path.write_text(job_path.read_text().replace("thumbnail_dpi: 72", "thumbnail_dpi: 36"), encoding="utf-8")
    return load_job(job_path), project


def _inventory(job, uncertain: bool = False) -> Path:
    draft = job.evidence_dir / "agent-output" / "inventory-draft.json"
    write_json(draft, {
        "spec": "pdf-extractor-pdf/inventory-draft@1.0",
        "role": "finder_agent",
        "reviewed_all_pages": True,
        "source_sha256": source_sha256(job.source),
        "page_findings": [
            {"page": 1, "label": "uncertain" if uncertain else "table", "notes": "start"},
            {"page": 2, "label": "continuation", "notes": "continued"},
        ],
        "tables": [{
            "id": "example", "title": "Example",
            "segments": [
                {"id": "segment-01", "page": 1, "bbox": [30, 40, 270, 150]},
                {"id": "segment-02", "page": 2, "bbox": [30, 40, 270, 150]},
            ],
        }],
    })
    return draft


def audit_and_attest(job, draft: Path) -> Path:
    report = audit_inventory(job, draft)
    overlays = {(x["table_id"], x["segment_id"]): x["overlay_sha256"] for x in report["segments"]}
    value = read_json(draft)
    for table in value["tables"]:
        for segment in table["segments"]:
            segment["bbox_review"] = {
                "overlay_sha256": overlays[(table["id"], segment["id"])],
                "all_visible_table_content_inside": True,
                "reviewed_edges": ["left", "right", "top", "bottom"],
            }
    write_json(draft, value)
    assert audit_inventory(job, draft)["passed"] is True
    return draft


def _reference(job, missing_boundary: bool = False) -> Path:
    samples = [
        {"row_index": 0, "values": ["Alpha", "1"]},
        {"row_index": 1, "values": ["Beta", "2"]},
        {"row_index": 2, "values": ["Gamma", "3"]},
    ]
    if missing_boundary:
        samples.pop(1)
    path = job.evidence_dir / "agent-output" / "reference-draft.json"
    write_json(path, {
        "spec": "pdf-extractor-pdf/reference-draft@1.0",
        "role": "qa_agent", "independent_from_extractor": True, "source_evidence_only": True,
        "source_sha256": source_sha256(job.source),
        "inventory_sha256": artifact_hash(job.inventory),
        "tables": [{
            "id": "example", "columns": ["Name", "Value"], "row_count": 3,
            "segment_row_counts": [2, 1], "samples": samples,
        }],
    })
    return path


def _write_extractor(job) -> None:
    digest = source_sha256(job.source)
    job.main.write_text(f'''from pathlib import Path
from pdf_extractor_pdf import *
def extract(source: Path, inventory: dict):
    rows = [["Alpha", "1"], ["Beta", "2"], ["Gamma", "3"]]
    provenance = [
        RowProvenance(1, (35, 70, 265, 90), "segment-01"),
        RowProvenance(1, (35, 90, 265, 115), "segment-01"),
        RowProvenance(2, (35, 70, 265, 95), "segment-02"),
    ]
    return ExtractionResult("{digest}", [ExtractedTable("example", "Example", ["Name", "Value"], rows, provenance)])
if __name__ == "__main__": project_entry(extract)
''', encoding="utf-8")


def test_full_workflow_reaches_both_hard_gates(tmp_path: Path) -> None:
    job, project = _fixture(tmp_path)
    assert prepare(job)["cache_hit"] is False
    assert prepare(job)["cache_hit"] is True
    start_stage(job.evidence_dir, "discovery", "finder_agent", "test", "finder", "finder-1")
    freeze_inventory(job, audit_and_attest(job, _inventory(job)))
    finish_stage(job.evidence_dir, "finder", "completed")
    manifest = inspect_inventory(job)
    assert len(manifest["segments"]) == 2
    start_stage(job.evidence_dir, "extraction", "extraction_agent", "test", "extraction", "extractor-1")
    start_stage(job.evidence_dir, "qa", "qa_agent", "test", "qa", "qa-1")
    _write_extractor(job)
    freeze_reference(job, _reference(job))
    finish_stage(job.evidence_dir, "qa", "completed")
    finish_stage(job.evidence_dir, "extraction", "completed")
    start_stage(job.evidence_dir, "extraction", "extraction_agent", "test", "extraction-repair", "extractor-1")
    finish_stage(job.evidence_dir, "extraction-repair", "completed")
    assert len(execute(job)["tables"]) == 1
    report = validate(job)
    assert report["passed"] and report["deterministic"]
    start_stage(job.evidence_dir, "review", "main_agent", "test", "main", "main-1")
    finish_stage(job.evidence_dir, "main", "completed")
    final = finalize(job)
    assert final["status"] == "machine_complete_not_human_approved"
    assert final["role_separation"]["extraction_qa_overlapped"] is True
    assert len(final["role_separation"]["dispatches"]) == 5
    assert check_existing(job)["passed"] is True
    assert verify_cache(job)["ok"] is True
    assert load_state(job.evidence_dir)["phase"] == "complete"
    assert sorted(path.name for path in (project / "output").iterdir()) == ["example.csv", "result.json"]
    assert not (job.main.parent / "__pycache__").exists()


def test_uncertain_page_blocks_hard_gate_1(tmp_path: Path) -> None:
    job, _ = _fixture(tmp_path)
    prepare(job)
    with pytest.raises(ValueError, match="uncertain pages"):
        freeze_inventory(job, _inventory(job, uncertain=True))


def test_reference_requires_cross_page_boundary_samples(tmp_path: Path) -> None:
    job, _ = _fixture(tmp_path)
    prepare(job)
    freeze_inventory(job, audit_and_attest(job, _inventory(job)))
    inspect_inventory(job)
    with pytest.raises(ValueError, match="required sample"):
        freeze_reference(job, _reference(job, missing_boundary=True))


def test_required_samples_include_middle_and_boundaries() -> None:
    assert required_sample_indices(13, [8, 5]) == [0, 1, 6, 7, 8, 11, 12]


def test_review_packet_is_compact_and_source_grounded(tmp_path: Path) -> None:
    job, _ = _fixture(tmp_path)
    prepare(job)
    freeze_inventory(job, audit_and_attest(job, _inventory(job)))
    inspect_inventory(job)
    draft = _reference(job)
    value = read_json(draft)
    value["tables"][0]["samples"][1]["values"] = ["Different", "2"]
    write_json(draft, value)
    freeze_reference(job, draft)
    _write_extractor(job)
    report = validate(job)
    issue = next(item for item in report["issues"] if item["code"] == "sample_mismatch")
    assert report["review_target"] == "main_agent"
    assert report["summary"]["case_count"] == 1
    assert report["review_cases"][0]["issue_ids"] == [issue["id"]]
    assert report["review_queue"] == [{"kind": "case", "id": "case::example"}]
    assert issue["extractor_sample"] == ["Beta", "2"]
    assert issue["qa_reference"] == ["Different", "2"]
    assert issue["cell_diffs"][0]["extractor_normalized"] == "Beta"
    evidence = report["evidence_index"][issue["evidence_refs"][0]]
    assert evidence["image"].endswith(".png")
