from __future__ import annotations

import json
from pathlib import Path

import pymupdf

from pdf_table_5.api import initialize


def make_pdf(path: Path, page_count: int = 1) -> None:
    document = pymupdf.open()
    for number in range(page_count):
        page = document.new_page(width=300, height=200)
        page.insert_text((30, 40), f"Page {number + 1} Header A Header B")
    document.save(path)


def test_initialize_creates_public_project_contract(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    project = tmp_path / "project"
    make_pdf(source)

    job = initialize(source, project)

    assert job["pdfInfo"]["totalPages"] == 1
    assert job["pdfInfo"]["sha256"]
    assert (project / "parse/main.py").is_file()
    assert (project / "parse/helper/param.json").is_file()
    assert (project / "parse/helper/states.json").is_file()
    assert (project / "parse/helper/steps.jsonl").is_file()
    assert not (project / "parse/helper/lock_sample.py").exists()
    state = json.loads((project / "parse/helper/states.json").read_text())
    assert state["currentTableIndex"] == -1
    params = json.loads((project / "parse/helper/param.json").read_text())
    assert params["agentModel"] == "gpt-5.6-terra"
    assert params["agentReasoningEffort"] == "medium"
    assert params["bboxMarginPt"] == 72
    guidance = (project / "AGENTS.md").read_text()
    assert "generated extraction data" in guidance
    assert "workflow skills" in guidance


def test_initialize_preserves_existing_project_agent_guidance(tmp_path: Path) -> None:
    source, project = tmp_path / "source.pdf", tmp_path / "project"
    make_pdf(source)
    project.mkdir()
    (project / "AGENTS.md").write_text("user-owned guidance", encoding="utf-8")
    initialize(source, project)
    assert (project / "AGENTS.md").read_text() == "user-owned guidance"


def test_initialize_records_selected_pages(tmp_path: Path) -> None:
    source, project = tmp_path / "source.pdf", tmp_path / "project"
    make_pdf(source, page_count=3)

    job = initialize(source, project, pages="1,3")

    assert job["pdfInfo"]["totalPages"] == 3
    assert job["demand"]["targetPages"] == [1, 3]


def test_existing_project_rejects_changed_page_selection(tmp_path: Path) -> None:
    source, project = tmp_path / "source.pdf", tmp_path / "project"
    make_pdf(source, page_count=3)
    initialize(source, project, pages="1")

    try:
        initialize(source, project, pages="2")
    except ValueError as exc:
        assert "page selection" in str(exc)
    else:
        raise AssertionError("changed page selection should fail")
