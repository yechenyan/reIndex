from __future__ import annotations

from copy import deepcopy

import json
import pytest

import pdf_to_markdown.workflow as workflow_module
from pdf_to_markdown.workflow import Workflow


def test_report_becomes_accepted_only_after_output_write(tmp_path, monkeypatch) -> None:
    source = tmp_path / "input.pdf"
    source.write_bytes(b"test pdf payload")
    output = tmp_path / "output.md"
    reports = []
    monkeypatch.setattr(
        workflow_module,
        "parse_pdf",
        lambda *_args, **_kwargs: {"markdown": "document", "pages": []},
    )
    monkeypatch.setattr(workflow_module, "discover", lambda _liteparse: [])
    monkeypatch.setattr(workflow_module, "render_candidates", lambda *_args: {})

    original_write_json = workflow_module.write_json

    def capture_report(path, value):
        if path.name == "report.json":
            reports.append(deepcopy(value))
        original_write_json(path, value)

    monkeypatch.setattr(workflow_module, "write_json", capture_report)
    result = Workflow(
        source, output, tmp_path / "work", model="test", reasoning_effort="medium"
    ).run()

    assert [report["accepted"] for report in reports] == [False, True]
    assert result["accepted"] is True
    assert output.read_text(encoding="utf-8") == "document"


def test_unverified_specialist_still_writes_output_and_final_report(tmp_path, monkeypatch) -> None:
    source = tmp_path / "input.pdf"
    source.write_bytes(b"test pdf payload")
    output = tmp_path / "output.md"
    candidate = {
        "tableId": "table_0001", "route": "specialist", "status": "pending",
        "pages": [1], "spans": [[0, 8]], "pageBounds": [[0, 8]], "routeReasons": [],
    }
    monkeypatch.setattr(
        workflow_module, "parse_pdf", lambda *_args, **_kwargs: {"markdown": "original", "pages": []}
    )
    monkeypatch.setattr(workflow_module, "discover", lambda _liteparse: [candidate])
    monkeypatch.setattr(workflow_module, "render_candidates", lambda *_args: {})

    def failed_specialist(*_args, **_kwargs):
        candidate["status"] = "specialist_failed"
        candidate["routeReasons"].append("confirmed sample is invalid")
        return {"pages": [1], "report": {"accepted": False}, "replacements": [],
                "unmatched": [], "failed": ["table_0003"]}

    monkeypatch.setattr(workflow_module, "run_specialist", failed_specialist)
    workflow = Workflow(source, output, tmp_path / "work", model="test", reasoning_effort="medium")

    with pytest.raises(RuntimeError, match="completed with unverified tables"):
        workflow.run()

    report = json.loads((tmp_path / "work" / "report.json").read_text())
    assert output.read_text(encoding="utf-8") == "original"
    assert report["accepted"] is False
    assert report["outputPath"] == str(output)
    assert report["failedStage"] == "specialist"
    assert report["failedSpecialistTables"] == ["table_0003"]
    assert report["errors"] == ["confirmed sample is invalid"]
