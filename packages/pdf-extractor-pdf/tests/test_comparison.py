from __future__ import annotations

from pathlib import Path

import pytest

from pdf_extractor_pdf.artifacts import read_json, write_json
from pdf_extractor_pdf.cell_diff import blocking_diffs, cell_diffs
from pdf_extractor_pdf.evidence import prepare
from pdf_extractor_pdf.inspection import inspect_inventory
from pdf_extractor_pdf.inventory import freeze_inventory
from pdf_extractor_pdf.reference import freeze_reference
from pdf_extractor_pdf.validation import validate
from test_workflow import _fixture, _inventory, _reference, _write_extractor, audit_and_attest


def test_text_mode_ignores_separators_but_preserves_order() -> None:
    equivalent = cell_diffs(
        ["Mecklenburg-\nVorpommern"], ["Mecklenburg Vorpommern"], ["text"],
    )
    assert equivalent[0]["difference_kind"] == "format_only"
    assert blocking_diffs(equivalent) == []
    reordered = cell_diffs(
        ["Engpass einen beheben"], ["einen Engpass beheben"], ["text"],
    )
    assert blocking_diffs(reordered)[0]["difference_kind"] == "value_difference"


def test_exact_mode_does_not_hide_numeric_punctuation() -> None:
    diffs = cell_diffs(["1,5"], ["15"], ["exact"])
    assert blocking_diffs(diffs)


def test_format_only_difference_passes_validation_and_is_reported(tmp_path: Path) -> None:
    job, _ = _fixture(tmp_path)
    prepare(job)
    freeze_inventory(job, audit_and_attest(job, _inventory(job)))
    inspect_inventory(job)
    draft = _reference(job)
    value = read_json(draft)
    value["tables"][0]["comparison_modes"] = ["text", "exact"]
    value["tables"][0]["samples"][1]["values"][0] = "Beta-Test"
    write_json(draft, value)
    freeze_reference(job, draft)
    _write_extractor(job)
    job.main.write_text(job.main.read_text().replace('["Beta", "2"]', '["Beta Test", "2"]'), encoding="utf-8")
    report = validate(job)
    assert report["passed"] is True
    assert report["summary"]["format_difference_count"] == 1
    assert report["format_differences"][0]["cell_diffs"][0]["content_equal"] is True


def test_empty_qa_cell_requires_explicit_source_blank(tmp_path: Path) -> None:
    job, _ = _fixture(tmp_path)
    prepare(job)
    freeze_inventory(job, audit_and_attest(job, _inventory(job)))
    inspect_inventory(job)
    draft = _reference(job)
    value = read_json(draft)
    value["tables"][0]["samples"][0]["values"][0] = ""
    write_json(draft, value)
    with pytest.raises(ValueError, match="explicitly declared source blank"):
        freeze_reference(job, draft)
    value["tables"][0]["samples"][0]["source_blank_indices"] = [0]
    write_json(draft, value)
    frozen = freeze_reference(job, draft)
    assert frozen["tables"][0]["samples"][0]["source_blank_indices"] == [0]


def test_reference_rejects_column_count_different_from_inventory(tmp_path: Path) -> None:
    job, _ = _fixture(tmp_path)
    prepare(job)
    freeze_inventory(job, audit_and_attest(job, _inventory(job)))
    inspect_inventory(job)
    draft = _reference(job)
    value = read_json(draft)
    value["tables"][0]["column_count"] = 3
    write_json(draft, value)
    with pytest.raises(ValueError, match="match frozen Inventory"):
        freeze_reference(job, draft)
