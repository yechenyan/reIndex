from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pymupdf

from pdf_table_5.api import initialize
from pdf_table_5.context import Context, Paths
from pdf_table_5.io import write_json
from pdf_table_5.repair_state import begin_repair, complete_repair, record_parser, table_snapshot
from pdf_table_5.state import initial_state
from pdf_table_5.table_workflow import review_with_repairs
from pdf_table_5.taskReportTable import failed_item, final_item
from pdf_table_5.workflow import Workflow


def test_empty_document_table_run_is_accepted(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.pdf"
    project = tmp_path / "project"
    document = pymupdf.open()
    document.new_page()
    document.save(source)
    initialize(source, project)

    monkeypatch.setattr("pdf_table_5.workflow.find_tables", lambda context: ({"tables": []}, {}))
    monkeypatch.setattr("pdf_table_5.workflow.merge_tables", lambda context, found: ({"tables": []}, {}))

    report = Workflow(project).run()

    assert report["accepted"] is True
    assert report["tableCount"] == 0
    assert (project / "output/finalTable.json").is_file()
    assert (project / "parse/report/report.md").is_file()


def test_workflow_isolates_one_table_exception_and_continues(tmp_path: Path, monkeypatch) -> None:
    paths = Paths(tmp_path)
    for directory in (paths.helper, paths.report, paths.output, paths.strategy):
        directory.mkdir(parents=True, exist_ok=True)
    write_json(paths.states, initial_state())
    workflow = Workflow(tmp_path)
    listed = {"tables": [
        {"parseTableId": "table_0000", "title": "Broken"},
        {"parseTableId": "table_0001", "title": "Good"},
    ]}
    captured = {}
    monkeypatch.setattr(workflow, "validate_job", lambda: None)
    monkeypatch.setattr("pdf_table_5.workflow.find_tables", lambda _context: ({"tables": []}, {}))
    monkeypatch.setattr("pdf_table_5.workflow.merge_tables", lambda _context, _found: ({"tables": []}, {}))
    monkeypatch.setattr("pdf_table_5.workflow.list_tables", lambda *_args: listed)
    monkeypatch.setattr("pdf_table_5.workflow.prepare_table", lambda _context, item: item)

    def parser(_context, table_id, _packet):
        if table_id == "table_0000":
            raise ValueError("bad generated sample")
        return {}

    monkeypatch.setattr("pdf_table_5.workflow.ensure_parser", parser)
    monkeypatch.setattr(
        "pdf_table_5.workflow.review_with_repairs",
        lambda _context, table_id: {
            "parseTableId": table_id, "title": "Good", "status": "verified",
            "accepted": True, "errors": [], "outputPath": "good.csv", "rowCount": 2,
        },
    )

    def report(_context, table_ids):
        captured["table_ids"] = table_ids
        return {"accepted": False, "tableCount": len(table_ids)}

    monkeypatch.setattr("pdf_table_5.workflow.report_tables", report)
    monkeypatch.setattr("pdf_table_5.workflow.refresh_metrics", lambda _context, report: report)

    result = workflow._run()

    assert result["accepted"] is False
    assert captured["table_ids"] == ["table_0000", "table_0001"]
    progress = json.loads((paths.helper / "finalTable.json").read_text())["tables"]
    assert progress[0]["errors"] == ["ValueError: bad generated sample"]
    assert progress[1]["accepted"] is True


def test_final_item_accepts_string_surrounding_text(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    table = paths.table_dir("table_0000")
    table.mkdir(parents=True)
    write_json(table / "table.json", {"tables": []})
    write_json(table / "summary.json", {"surroundingText": "plain context"})
    review = {"parseTableId": "table_0000", "title": "", "status": "verified", "accepted": True, "errors": []}
    item = final_item(Context(paths), review)
    assert item["textBefore"] == ""
    assert item["textAfter"] == ""


def test_repair_budget_and_session_persist_across_resume(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    paths.helper.mkdir(parents=True)
    write_json(paths.states, initial_state())
    context = Context(paths)
    record_parser(context, "table_0000", "session-a")
    attempt, state = begin_repair(context, "table_0000", 2)
    assert attempt == 1
    assert state["parserSessionId"] == "session-a"
    complete_repair(context, "table_0000", "session-a")
    attempt, _ = begin_repair(Context(paths), "table_0000", 2)
    assert attempt == 2
    complete_repair(Context(paths), "table_0000", "session-a")
    assert begin_repair(Context(paths), "table_0000", 2) is None
    assert table_snapshot(Context(paths), "table_0000")["repairAttemptsStarted"] == 2


def test_failed_table_report_includes_persisted_attempts(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    paths.helper.mkdir(parents=True)
    table = paths.table_dir("table_0000")
    table.mkdir(parents=True)
    write_json(paths.states, initial_state())
    write_json(table / "table.json", {"tables": [{"page": 7, "bbox": [0, 0, 1, 1]}]})
    context = Context(paths)
    record_parser(context, "table_0000", "session-a")
    begin_repair(context, "table_0000", 3)
    item = failed_item(
        context,
        {"parseTableId": "table_0000", "title": "Bad", "accepted": False,
         "errors": ["no rows"], "outputPath": None},
    )
    assert item["attemptsUsed"] == 1
    assert item["pages"] == [7]


def test_repair_resumes_parser_session_and_patches_only_code(tmp_path: Path, monkeypatch) -> None:
    paths = Paths(tmp_path)
    table = paths.table_dir("table_0000")
    for directory in (paths.helper, table, paths.strategy, paths.report, paths.output):
        directory.mkdir(parents=True, exist_ok=True)
    paths.steps.touch()
    source = tmp_path / "source.pdf"
    source.write_bytes(b"pdf")
    write_json(paths.job, {"demand": {"inputPath": str(source)}})
    write_json(paths.states, initial_state())
    write_json(table / "segment.json", {"words": [{"bbox": [0, 0, 1, 1], "text": "x"}]})
    packet = {
        "parseTableId": "table_0000", "projectRoot": str(tmp_path), "sourcePdf": str(source),
        "tables": [{"page": 1, "bbox": [0, 0, 1, 1], "geometry": "parse/tables/table_0000/segment.json",
                    "screenshot": "missing.png", "contextScreenshot": "missing-context.png"}],
    }
    write_json(table / "table.json", packet)
    sample = {"mode": "content", "totalRows": 2, "header": ["A"],
              "rows": [{"rowIndex": 1, "values": ["x"]}], "skipReason": ""}
    summary = {"title": "T", "classification": "vector", "pages": [1], "bboxes": [[0, 0, 1, 1]],
               "surroundingText": {"before": "", "after": ""}, "imageTable": False, "skipped": False,
               "skipReason": "", "strategy": "", "sqlFriendly": True, "extractionDpi": 216, "steps": []}
    (table / "sample.py").write_text(sample_program(sample), encoding="utf-8")
    write_json(table / "summary.json", summary)
    (table / "parse.py").write_text(csv_parser([["A"]]), encoding="utf-8")
    record_parser(Context(paths), "table_0000", "session-a")
    captured = {}

    def fake_agent(*args, **kwargs):
        captured["session_id"] = kwargs.get("session_id")
        captured["images"] = kwargs.get("images")
        captured["prompt"] = args[2]
        payload = {"diagnosis": "add row", "baseRevision": 1,
                   "changes": {"samplePy": None, "summary": None, "parsePy": csv_parser([["A"], ["x"]]),
                               "strategyFileName": None, "strategyPy": None}}
        return SimpleNamespace(payload=payload, token_usage={}, session_id="session-a")

    monkeypatch.setattr("pdf_table_5.table_workflow.run_agent", fake_agent)
    review = review_with_repairs(Context(paths), "table_0000")
    assert review["status"] == "verified"
    assert captured["session_id"] == "session-a"
    assert [path.name for path in captured["images"]] == ["missing.png"]
    assert captured["prompt"].startswith("PDF-TABLE-5 RESUMED SESSION DELTA")
    assert table_snapshot(Context(paths), "table_0000")["repairAttemptsStarted"] == 1
    steps = [json.loads(line) for line in paths.steps.read_text().splitlines()]
    repair = next(step for step in steps if step["type"] == "repair-table_0000-1")
    assert repair["details"]["changedArtifacts"] == ["parsePy"]


def csv_parser(rows: list[list[str]]) -> str:
    return (
        "import argparse,csv\n"
        "p=argparse.ArgumentParser();p.add_argument('--table-json');p.add_argument('--output');a=p.parse_args()\n"
        f"rows={rows!r}\n"
        "with open(a.output,'w',encoding='utf-8',newline='') as f: csv.writer(f).writerows(rows)\n"
    )


def sample_program(sample: dict) -> str:
    return "import json\nSAMPLE=" + repr(sample) + "\nprint(json.dumps(SAMPLE,ensure_ascii=False))\n"
