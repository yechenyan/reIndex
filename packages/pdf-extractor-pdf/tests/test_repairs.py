from __future__ import annotations

from pathlib import Path

from pdf_extractor_pdf.evidence import prepare
from pdf_extractor_pdf.gates import finalize
from pdf_extractor_pdf.inspection import inspect_inventory
from pdf_extractor_pdf.inventory import freeze_inventory
from pdf_extractor_pdf.reference import freeze_reference
from pdf_extractor_pdf.repairs import begin_qa_repair
from pdf_extractor_pdf.repair_scope import create_repair_scope
from pdf_extractor_pdf.validation import validate
from test_workflow import (
    _fixture,
    _inventory,
    _reference,
    _write_extractor,
    audit_and_attest,
)


def test_begin_qa_repair_is_resumable_and_preserves_review_history(tmp_path: Path) -> None:
    job, _ = _fixture(tmp_path)
    prepare(job)
    freeze_inventory(job, audit_and_attest(job, _inventory(job)))
    inspect_inventory(job)
    freeze_reference(job, _reference(job))
    _write_extractor(job)
    report = validate(job)
    archive = Path(report["review_archive"])
    first = begin_qa_repair(job, ["example"])
    assert first["repair_status"] == "created"
    assert archive.is_file() and not (job.evidence_dir / "review.json").exists()
    second = begin_qa_repair(job, ["example"])
    assert second["repair_status"] == "resumed"


def test_completed_extraction_scope_can_validate_without_reopening_qa(tmp_path: Path) -> None:
    job, _ = _fixture(tmp_path)
    job.policy["require_independent_agents"] = False
    prepare(job)
    freeze_inventory(job, audit_and_attest(job, _inventory(job)))
    inspect_inventory(job)
    freeze_reference(job, _reference(job))
    _write_extractor(job)
    assert validate(job)["passed"] is True
    finalize(job)
    create_repair_scope(job, "extraction_agent", ["example"])
    report = validate(job)
    assert report["passed"] is True
    assert report["review_sequence"] == 2
