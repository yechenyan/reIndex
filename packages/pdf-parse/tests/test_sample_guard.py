from pathlib import Path

from pdf_parse.sample_guard import run_visual_sample


def test_fixed_visual_sample_runs_without_input(tmp_path: Path):
    script = tmp_path / "sample.py"
    script.write_text(
        """import argparse, json
p = argparse.ArgumentParser()
p.add_argument('--table-json', required=True)
p.parse_args()
print(json.dumps({'mode': 'sample', 'rows': [{'physicalRow': 1, 'values': ['A', 3]}], 'totalPhysicalRows': 1, 'compareRules': [], 'skipReason': ''}))
""",
        encoding="utf-8",
    )
    sample, errors = run_visual_sample(script)
    assert errors == []
    assert sample["rows"][0]["values"] == ["A", 3]


def test_sample_cannot_read_table_json(tmp_path: Path):
    script = tmp_path / "sample.py"
    script.write_text(
        """import argparse, json
p = argparse.ArgumentParser()
p.add_argument('--table-json', required=True)
a = p.parse_args()
with open(a.table_json) as f:
    value = json.load(f)
print(json.dumps(value))
""",
        encoding="utf-8",
    )
    _, errors = run_visual_sample(script)
    assert any("exited" in error for error in errors)


def test_sample_rejects_nonempty_compare_rules(tmp_path: Path):
    script = tmp_path / "sample.py"
    script.write_text(
        """import json
print(json.dumps({'mode': 'sample', 'rows': [{'physicalRow': 1, 'values': ['A']}], 'totalPhysicalRows': 1, 'compareRules': {'0': 'numeric'}, 'skipReason': ''}))
""",
        encoding="utf-8",
    )
    _, errors = run_visual_sample(script)
    assert "Sample compareRules must be an empty array; all cells use LCS" in errors
