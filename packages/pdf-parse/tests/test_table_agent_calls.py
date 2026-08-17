from pathlib import Path

from pdf_parse import table_agent_calls
from pdf_parse.agent_cli import AgentResult
from pdf_parse.paths import ProjectPaths


def capture_call(tmp_path, monkeypatch, errors):
    captured = {}

    def fake_run_agent(**kwargs):
        captured.update(kwargs)
        return AgentResult({}, "session", {}, "")

    monkeypatch.setattr(table_agent_calls, "run_agent", fake_run_agent)
    table_agent_calls.table_call(
        ProjectPaths(tmp_path),
        {"pdfPath": "secret.pdf", "geometry": {"large": True}},
        [Path("table.png")],
        {"model": "model", "reasoningEffort": "medium"},
        "session",
        {},
        errors,
        {"rows": [["A"], ["B"]]},
        {"rows": [{"physicalRow": 1, "values": ["A"]}]},
    )
    return captured


def test_code_repair_sends_no_images_or_geometry(tmp_path, monkeypatch):
    captured = capture_call(tmp_path, monkeypatch, ["parse.py syntax error: invalid syntax"])
    assert captured["images"] == []
    assert "secret.pdf" not in captured["prompt"]
    assert '"repairMode":"code_repair"' in captured["prompt"]


def test_lcs_conflict_reuses_session_image_without_resending(tmp_path, monkeypatch):
    captured = capture_call(
        tmp_path,
        monkeypatch,
        ["Physical row 2 column 1 LCS=20.0% below 80%"],
    )
    assert captured["images"] == []
    assert "secret.pdf" not in captured["prompt"]
    assert '"repairMode":"visual_recheck"' in captured["prompt"]


def test_rerender_sends_new_images_without_repeating_geometry(tmp_path, monkeypatch):
    captured = {}

    def fake_run_agent(**kwargs):
        captured.update(kwargs)
        return AgentResult({}, "session", {}, "")

    monkeypatch.setattr(table_agent_calls, "run_agent", fake_run_agent)
    context = {
        "pdfPath": "secret.pdf",
        "requestedDpi": 600,
        "dpiBounds": {"minDpi": 72, "maxDpi": 600},
        "evidence": [{"actualDpi": 600}],
        "latestGeometry": {"revision": "sha256:abc", "large": True},
    }
    table_agent_calls.table_call(
        ProjectPaths(tmp_path), context, [Path("new.png")],
        {"model": "model", "reasoningEffort": "medium"},
        "session", rerender_update=True,
    )

    assert captured["images"] == [Path("new.png")]
    assert "secret.pdf" not in captured["prompt"]
    assert '"geometryRevision":"sha256:abc"' in captured["prompt"]
    assert '"large":true' not in captured["prompt"]
