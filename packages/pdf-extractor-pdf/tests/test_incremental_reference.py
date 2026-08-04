from __future__ import annotations

from pathlib import Path

from pdf_extractor_pdf.artifacts import read_json, write_json
from pdf_extractor_pdf.evidence import prepare
from pdf_extractor_pdf.inspection import inspect_inventory
from pdf_extractor_pdf.inventory import freeze_inventory, reopen_inventory
from pdf_extractor_pdf.reference_scaffold import plan_reference, scaffold_reference
from test_workflow import _fixture, _inventory, audit_and_attest


def test_inspect_reuses_only_unchanged_segment(tmp_path) -> None:
    job, _ = _fixture(tmp_path)
    prepare(job)
    draft = _inventory(job)
    freeze_inventory(job, audit_and_attest(job, draft))
    first = inspect_inventory(job)
    old_images = [item["image"] for item in first["segments"]]
    reopen_inventory(job, "adjust one crop")
    changed = read_json(draft)
    changed["tables"][0]["segments"][1]["bbox"] = [35, 40, 270, 150]
    write_json(draft, changed)
    freeze_inventory(job, audit_and_attest(job, draft))
    second = inspect_inventory(job)
    assert second["reused_segments"] == 1
    assert second["rendered_segments"] == 1
    assert second["segments"][0]["image"] == old_images[0]
    assert second["segments"][1]["image"] != old_images[1]


def test_reference_structure_generates_adaptive_sample_template(tmp_path) -> None:
    job, _ = _fixture(tmp_path)
    prepare(job)
    draft = _inventory(job)
    freeze_inventory(job, audit_and_attest(job, draft))
    inspect_inventory(job)
    scaffold = scaffold_reference(job)
    structure = read_json(Path(scaffold["path"]))
    structure["spec"] = "pdf-extractor-pdf/reference-structure-draft@2.0"
    assert structure["tables"][0]["column_count"] == 2
    structure["tables"][0]["comparison_modes"] = ["text", "exact"]
    structure["tables"][0]["segments"][0]["source_row_count"] = 2
    structure["tables"][0]["segments"][1]["source_row_count"] = 2
    structure["tables"][0]["segments"][1]["repeated_leading_rows"] = 1
    draft = job.evidence_dir / "reference-work" / "structure-draft.json"
    write_json(draft, structure)
    planned = read_json(Path(plan_reference(job, draft)["path"]))
    assert planned["tables"][0]["row_count"] == 3
    assert planned["tables"][0]["segment_repeated_leading_rows"] == [0, 1]
    assert planned["tables"][0]["comparison_modes"] == ["text", "exact"]
    assert [item["row_index"] for item in planned["tables"][0]["samples"]] == [0, 1, 2]
    assert "segment_boundary_before" in planned["tables"][0]["samples"][1]["reasons"]
