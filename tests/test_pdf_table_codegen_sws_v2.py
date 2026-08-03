from __future__ import annotations

from pathlib import Path

from pdf_table_codegen.artifacts import artifact_hash, read_json
from pdf_table_codegen.job import load_job
from pdf_table_codegen.workflow import load_state

PROJECT = (
    Path(__file__).parents[1]
    / "testbase/test5-table/sws-netze-solingen-2024/project"
)


def test_sws_v2_frozen_project_is_machine_complete() -> None:
    job = load_job(PROJECT / "job.yaml")
    state = load_state(job.evidence_dir)
    verification = read_json(job.output_dir / "verification.json")
    result = read_json(job.output_dir / "result.json")
    assert state["phase"] == "machine_complete"
    assert verification["spec"] == "pdf-table-codegen/verification@2.0"
    assert verification["ok"] is True
    assert len(verification["checks"]) == 56
    assert [(len(table["rows"]), len(table["headers"])) for table in result["tables"]] == [
        (25, 2), (5, 3), (7, 6), (6, 4), (6, 4), (13, 16)
    ]
    assert artifact_hash(job.extractor) == verification["extractor_sha256"]
    assert artifact_hash(job.inventory) == verification["inventory_sha256"]
    assert artifact_hash(job.reference) == verification["reference_sha256"]
    for name, digest in verification["output_hashes"].items():
        assert artifact_hash(job.output_dir / name) == digest
    assert not (PROJECT / "__pycache__").exists()
