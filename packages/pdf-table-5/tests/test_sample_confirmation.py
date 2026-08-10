from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from pdf_table_5.context import Context, Paths
from pdf_table_5.io import write_json
from pdf_table_5.repair_state import record_parser, table_snapshot
from pdf_table_5.state import initial_state
from pdf_table_5.table_workflow import review_with_repairs


def test_rule_only_sample_repair_does_not_start_confirmation(tmp_path: Path, monkeypatch) -> None:
    context, table = prepare(tmp_path, "Al-pha", "Alpha")
    calls = []

    def fake_agent(*args, **kwargs):
        calls.append(args[1])
        fixed = sample_program("Al-pha", rules=[{"kind": "ignore_space_hyphen", "columns": [0]}])
        return result(repair_payload(sample_py=fixed), "session-a")

    monkeypatch.setattr("pdf_table_5.table_workflow.run_agent", fake_agent)
    review = review_with_repairs(context, "table_0000")
    assert review["accepted"] is True
    assert calls == ["repair-table_0000"]
    assert not (table / "sampleConfirmation.json").exists()


def test_raw_sample_change_requires_source_only_new_agent(tmp_path: Path, monkeypatch) -> None:
    context, table = prepare(tmp_path, "Correct", "Wrong")
    calls, confirm_prompts, later_repair_prompts = [], [], []

    def fake_agent(*args, **kwargs):
        role = args[1]
        calls.append((role, kwargs.get("session_id")))
        if role == "sample-confirm-table_0000":
            confirm_prompts.append(args[2])
            return result(
                {"reason": "The PDF crop shows Correct.", "samplePy": sample_program("Correct")},
                "confirm-session",
            )
        repair_count = sum(name == "repair-table_0000" for name, _ in calls)
        if repair_count == 1:
            return result(repair_payload(sample_py=sample_program("Wrong")), "session-a")
        later_repair_prompts.append(args[2])
        return result(repair_payload(parse_py=csv_parser("Correct")), "session-a")

    monkeypatch.setattr("pdf_table_5.table_workflow.run_agent", fake_agent)
    monkeypatch.setattr("pdf_table_5.sample_confirmation.run_agent", fake_agent)
    review = review_with_repairs(context, "table_0000")

    assert review["accepted"] is True
    assert calls == [
        ("repair-table_0000", "session-a"),
        ("sample-confirm-table_0000", None),
        ("repair-table_0000", "session-a"),
    ]
    assert "Wrong" not in confirm_prompts[0]
    assert "totalRows includes the header" in confirm_prompts[0]
    assert "those borders override individual glyph" in confirm_prompts[0]
    assert "blank, `1`, `(0)`, blank" in confirm_prompts[0]
    assert "sampleSourceConfirmation" in later_repair_prompts[0]
    confirmation = json.loads((table / "sampleConfirmation.json").read_text())
    assert confirmation["decision"] == "keep_current"
    assert table_snapshot(context, "table_0000")["repairAttemptsCompleted"] == 2


def test_invalid_confirmation_uses_next_repair_instead_of_aborting(tmp_path: Path, monkeypatch) -> None:
    context, table = prepare(tmp_path, "Correct", "Wrong")
    calls = []

    def fake_agent(*args, **kwargs):
        role = args[1]
        calls.append(role)
        if role == "sample-confirm-table_0000":
            invalid_sample = {
                "mode": "content", "totalRows": 3, "header": ["Name"],
                "rows": [{"rowIndex": 1, "values": ["Wrong"]},
                         {"rowIndex": 3, "values": ["Wrong"]}], "skipReason": "",
            }
            invalid = "import json\nprint(json.dumps(" + repr(invalid_sample) + "))\n"
            return result({"reason": "miscounted", "samplePy": invalid}, "confirm-session")
        repair_count = calls.count("repair-table_0000")
        if repair_count == 1:
            return result(repair_payload(sample_py=sample_program("Wrong")), "session-a")
        return result(repair_payload(parse_py=csv_parser("Correct")), "session-a")

    monkeypatch.setattr("pdf_table_5.table_workflow.run_agent", fake_agent)
    monkeypatch.setattr("pdf_table_5.sample_confirmation.run_agent", fake_agent)
    review = review_with_repairs(context, "table_0000")

    assert review["accepted"] is True
    assert calls == ["repair-table_0000", "sample-confirm-table_0000", "repair-table_0000"]
    confirmation = json.loads((table / "sampleConfirmation.json").read_text())
    assert confirmation["decision"] == "rejected_invalid"
    assert "sample row indexes" in confirmation["errors"][0]
    assert table_snapshot(context, "table_0000")["repairAttemptsCompleted"] == 2


def test_invalid_current_sample_is_repaired_and_source_confirmed(tmp_path: Path, monkeypatch) -> None:
    context, table = prepare(tmp_path, "Correct", "Wrong")
    (table / "sample.py").write_text("this is not python !!!", encoding="utf-8")
    calls = []

    def fake_agent(*args, **kwargs):
        role = args[1]
        calls.append(role)
        if role == "sample-confirm-table_0000":
            assert '"currentSample":null' in args[2]
            return result(
                {"reason": "source shows Correct", "samplePy": sample_program("Correct")},
                "confirm-session",
            )
        return result(
            repair_payload(sample_py=sample_program("Correct"), parse_py=csv_parser("Correct")),
            "session-a",
        )

    monkeypatch.setattr("pdf_table_5.table_workflow.run_agent", fake_agent)
    monkeypatch.setattr("pdf_table_5.sample_confirmation.run_agent", fake_agent)

    review = review_with_repairs(context, "table_0000")

    assert review["accepted"] is True
    assert calls == ["repair-table_0000", "sample-confirm-table_0000"]
    confirmation = json.loads((table / "sampleConfirmation.json").read_text())
    assert confirmation["decision"] == "accept_proposed"


def prepare(tmp_path: Path, expected: str, actual: str) -> tuple[Context, Path]:
    paths = Paths(tmp_path)
    table = paths.table_dir("table_0000")
    for directory in (paths.helper, paths.strategy, paths.report, paths.output, table):
        directory.mkdir(parents=True, exist_ok=True)
    paths.steps.touch()
    source = tmp_path / "source.pdf"
    source.write_bytes(b"pdf")
    write_json(paths.job, {"demand": {"inputPath": str(source)}})
    write_json(paths.states, initial_state())
    geometry = table / "segment.json"
    write_json(geometry, {"words": [{"bbox": [0, 0, 1, 1], "text": expected}]})
    packet = {
        "parseTableId": "table_0000", "projectRoot": str(tmp_path), "sourcePdf": str(source),
        "tables": [{"page": 1, "bbox": [0, 0, 1, 1],
                    "geometry": "parse/tables/table_0000/segment.json",
                    "screenshot": "table.png", "contextScreenshot": "context.png"}],
    }
    write_json(table / "table.json", packet)
    (table / "sample.py").write_text(sample_program(expected), encoding="utf-8")
    write_json(table / "summary.json", summary())
    (table / "parse.py").write_text(csv_parser(actual), encoding="utf-8")
    context = Context(paths)
    record_parser(context, "table_0000", "session-a")
    return context, table


def sample_program(value: str, rules: list | None = None) -> str:
    sample = {
        "mode": "content", "totalRows": 2, "header": ["Name"],
        "rows": [{"rowIndex": 1, "values": [value]}], "skipReason": "",
    }
    if rules is not None:
        sample["compareRules"] = rules
    return "import json\nprint(json.dumps(" + repr(sample) + ", ensure_ascii=False))\n"


def csv_parser(value: str) -> str:
    return (
        "import argparse,csv\n"
        "p=argparse.ArgumentParser();p.add_argument('--table-json');p.add_argument('--output');a=p.parse_args()\n"
        f"rows={[['Name'], [value]]!r}\n"
        "with open(a.output,'w',encoding='utf-8',newline='') as f: csv.writer(f).writerows(rows)\n"
    )


def summary() -> dict:
    return {
        "title": "T", "classification": "vector", "pages": [1], "bboxes": [[0, 0, 1, 1]],
        "surroundingText": {"before": "", "after": ""}, "imageTable": False, "skipped": False,
        "skipReason": "", "strategy": "", "sqlFriendly": True, "extractionDpi": 216, "steps": [],
    }


def repair_payload(*, sample_py=None, parse_py=None) -> dict:
    return {
        "diagnosis": "repair", "baseRevision": 1 if sample_py is not None else 2,
        "changes": {"samplePy": sample_py, "summary": None, "parsePy": parse_py,
                    "strategyFileName": None, "strategyPy": None},
    }


def result(payload: dict, session_id: str) -> SimpleNamespace:
    return SimpleNamespace(payload=payload, token_usage={}, session_id=session_id)
