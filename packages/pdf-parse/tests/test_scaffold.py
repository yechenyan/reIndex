from pathlib import Path

from pdf_parse.io_utils import read_json
from pdf_parse.scaffold import initialize_project


def test_initialize_writes_python_project_contract(tmp_path: Path):
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    paths = initialize_project(pdf, tmp_path / "project")
    assert read_json(paths.params)["liteParse"] == {
        "version": "2.13.0",
        "ocrEnabled": False,
    }
    assert read_json(paths.params)["agents"] == {
        "model": "gpt-5.6-luna",
        "reasoningEffort": "medium",
        "maxRepairsPerTable": 5,
    }
    assert "def execute()" in (paths.parse / "main.py").read_text(encoding="utf-8")
