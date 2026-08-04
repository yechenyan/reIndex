from __future__ import annotations

from pathlib import Path

import fitz

from pdf_extractor_pdf.artifacts import read_json, write_json
from pdf_extractor_pdf.evidence import prepare
from pdf_extractor_pdf.inventory_audit import audit_inventory
from pdf_extractor_pdf.job import load_job
from pdf_extractor_pdf.models import source_sha256
from pdf_extractor_pdf.repair_scope import merge_reference_patch, scope_violations
from pdf_extractor_pdf.review_cases import build_review_cases
from pdf_extractor_pdf.scaffold import initialize_project
from test_workflow import _fixture, _inventory


def test_contact_sheets_repeat_previous_window_tail(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source = project / "source.pdf"
    document = fitz.open()
    for number in range(17):
        document.new_page(width=100, height=100).insert_text((10, 20), str(number + 1))
    document.save(source)
    document.close()
    job = load_job(initialize_project(project, source, "Find tables"))
    manifest = prepare(job)
    assert [x["pages"] for x in manifest["contact_windows"]] == [
        list(range(1, 9)), list(range(8, 16)), [15, 16, 17],
    ]


def test_inventory_audit_requires_overlay_token_and_blocks_clipped_word(tmp_path: Path) -> None:
    job, _ = _fixture(tmp_path)
    prepare(job)
    draft = _inventory(job)
    value = read_json(draft)
    value["tables"][0]["segments"][0]["bbox"] = [30, 40, 55, 150]
    write_json(draft, value)
    first = audit_inventory(job, draft)
    assert first["passed"] is False
    assert any(x["code"] == "clipped_word" for x in first["segments"][0]["blocking_signals"])
    overlays = {(x["table_id"], x["segment_id"]): x["overlay_sha256"] for x in first["segments"]}
    value = read_json(draft)
    for table in value["tables"]:
        for segment in table["segments"]:
            segment["bbox_review"] = {
                "overlay_sha256": overlays[(table["id"], segment["id"])],
                "all_visible_table_content_inside": True,
                "reviewed_edges": ["left", "right", "top", "bottom"],
            }
    write_json(draft, value)
    assert audit_inventory(job, draft)["passed"] is False


def test_repair_scope_protects_unaffected_tables_and_reuses_reference(tmp_path: Path) -> None:
    job, _ = _fixture(tmp_path)
    state = {
        "affected_table_ids": ["a"],
        "baseline": {
            "inventory_tables": {"a": {"id": "a"}, "b": {"id": "b", "title": "B"}},
            "reference_tables": {"a": {"id": "a", "row_count": 1}, "b": {"id": "b", "row_count": 2}},
            "result_tables": {"a": {"id": "a", "rows": [["1"]]}, "b": {"id": "b", "rows": [["2"]]}},
        },
    }
    write_json(job.evidence_dir / "repair-scope-state.json", state)
    merged = merge_reference_patch(job, {"a": {"id": "a", "row_count": 3}})
    assert merged == [{"id": "a", "row_count": 3}, {"id": "b", "row_count": 2}]
    issues = scope_violations(
        job, {"tables": [{"id": "a", "rows": [["9"]]}, {"id": "b", "rows": [["changed"]]}]},
        {"tables": [{"id": "a"}, {"id": "b", "title": "B"}]},
        {"tables": merged},
    )
    assert [(x["table_id"], x["artifact"]) for x in issues] == [("b", "result")]


def test_review_groups_table_errors_and_routes_structural_failures() -> None:
    issues = [
        {"id": "a:row_count", "code": "row_count_mismatch", "table_id": "a", "evidence_refs": ["a::s1"]},
        {"id": "a:sample:0", "code": "sample_mismatch", "table_id": "a", "evidence_refs": ["a::s1"]},
        {"id": "a:sample:1", "code": "sample_mismatch", "table_id": "a", "evidence_refs": ["a::s1"]},
    ]
    cases, plan = build_review_cases(issues)
    assert len(cases) == 1 and cases[0]["route"] == "extraction_agent"
    assert cases[0]["issue_ids"] == ["a:row_count", "a:sample:0", "a:sample:1"]
    assert plan == {"extraction_agent": ["a"]}
