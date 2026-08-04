from __future__ import annotations

from pathlib import Path

import fitz

from pdf_extractor_pdf.artifacts import artifact_hash, write_json
from pdf_extractor_pdf.decisions import resolve_merges
from pdf_extractor_pdf.evidence import prepare
from pdf_extractor_pdf.gates import finalize
from pdf_extractor_pdf.inspection import inspect_inventory
from pdf_extractor_pdf.inventory import freeze_inventory
from pdf_extractor_pdf.job import load_job
from pdf_extractor_pdf.models import source_sha256
from pdf_extractor_pdf.merge_detection import merge_candidates
from pdf_extractor_pdf.reference import freeze_reference
from pdf_extractor_pdf.scaffold import initialize_project
from pdf_extractor_pdf.validation import validate
from test_workflow import audit_and_attest


def test_source_evidenced_keep_separate_decision_unblocks_gate(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source = project / "source.pdf"
    document = fitz.open()
    for title in ["Network plan — section A", "Network plan — section B"]:
        page = document.new_page(width=300, height=200)
        page.draw_rect(fitz.Rect(30, 40, 270, 140))
        page.insert_text((40, 60), title)
    document.save(source)
    document.close()
    job_path = initialize_project(project, source, "Extract two distinct tables")
    job_path.write_text(job_path.read_text().replace("require_independent_agents: true", "require_independent_agents: false"))
    job = load_job(job_path)
    prepare(job)
    inventory_draft = job.evidence_dir / "inventory-draft.json"
    write_json(inventory_draft, {
        "spec": "pdf-extractor-pdf/inventory-draft@1.0", "role": "finder_agent",
        "reviewed_all_pages": True, "source_sha256": source_sha256(source),
        "page_findings": [
            {"page": 1, "label": "table", "notes": "A"},
            {"page": 2, "label": "continuation", "notes": "visually continuation-like"},
        ],
        "tables": [
            {"id": "table-a", "title": "Network plan", "segments": [{"id": "a1", "page": 1, "bbox": [30, 40, 270, 140]}]},
            {"id": "table-b", "title": "Network plan", "segments": [{"id": "b1", "page": 2, "bbox": [30, 40, 270, 140]}]},
        ],
    })
    freeze_inventory(job, audit_and_attest(job, inventory_draft))
    inspect_inventory(job)
    reference_draft = job.evidence_dir / "reference-draft.json"
    write_json(reference_draft, {
        "spec": "pdf-extractor-pdf/reference-draft@1.0", "role": "qa_agent",
        "independent_from_extractor": True, "source_evidence_only": True,
        "source_sha256": source_sha256(source), "inventory_sha256": artifact_hash(job.inventory),
        "tables": [
            {"id": "table-a", "columns": ["Name"], "row_count": 1, "segment_row_counts": [1], "samples": [{"row_index": 0, "values": ["A"]}]},
            {"id": "table-b", "columns": ["Name"], "row_count": 1, "segment_row_counts": [1], "samples": [{"row_index": 0, "values": ["B"]}]},
        ],
    })
    freeze_reference(job, reference_draft)
    digest = source_sha256(source)
    job.main.write_text(f'''from pathlib import Path
from pdf_extractor_pdf import *
def extract(source: Path, inventory: dict):
    tables = [
      ExtractedTable("table-a", "Table A", ["Name"], [["A"]], [RowProvenance(1, (35, 70, 260, 90), "a1")]),
      ExtractedTable("table-b", "Table B", ["Name"], [["B"]], [RowProvenance(2, (35, 70, 260, 90), "b1")]),
    ]
    return ExtractionResult("{digest}", tables)
if __name__ == "__main__": project_entry(extract)
''', encoding="utf-8")
    first = validate(job)
    assert first["passed"] is False and first["merge_candidates"][0]["confidence"] >= 0.85
    draft = job.evidence_dir / "merge-decisions-draft.json"
    write_json(draft, {
        "spec": "pdf-extractor-pdf/merge-decisions-draft@1.0", "role": "main_agent",
        "inventory_sha256": artifact_hash(job.inventory),
        "decisions": [{
            "left": "table-a", "right": "table-b", "decision": "keep_separate",
            "reason": "The source section labels name two distinct datasets.", "evidence_pages": [1, 2],
        }],
    })
    frozen = resolve_merges(job, draft)
    assert len(frozen["decisions"][0]["evidence"]) == 2
    second = validate(job)
    assert second["passed"] is True and second["merge_candidates"][0]["resolved"] is True
    assert finalize(job)["merge_decisions_sha256"] == artifact_hash(job.evidence_dir / "merge-decisions.json")


def test_distinct_table_numbers_suppress_layout_only_merge_candidate() -> None:
    inventory = {
        "page_findings": [{"page": 1, "label": "table"}, {"page": 2, "label": "table"}],
        "tables": [
            {"id": "a", "title": "Tabelle 3", "segments": [{"id": "a1", "page": 1}]},
            {"id": "b", "title": "Tabelle 4", "segments": [{"id": "b1", "page": 2}]},
        ],
    }
    result = {"tables": [{"id": "a", "columns": ["X"]}, {"id": "b", "columns": ["X"]}]}
    assert merge_candidates(result, inventory, 0.85, {}) == []
