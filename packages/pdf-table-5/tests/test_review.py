from __future__ import annotations

import json
from pathlib import Path

from pdf_table_5.context import Context, Paths
from pdf_table_5.io import write_json
from pdf_table_5.taskReviewTable import run
from pdf_table_5.parser_artifacts import current


PARSER = '''import argparse
import csv

parser = argparse.ArgumentParser()
parser.add_argument("--table-json")
parser.add_argument("--output")
args = parser.parse_args()
with open(args.output, "w", encoding="utf-8", newline="") as stream:
    writer = csv.writer(stream)
    writer.writerows([["Name", "Value"], ["Alpha", "1"], ["Beta", "2"]])
'''


def prepare(tmp_path: Path) -> tuple[Context, Path]:
    paths = Paths(tmp_path)
    table = paths.table_dir("table_0000")
    table.mkdir(parents=True)
    paths.output.mkdir()
    write_json(table / "table.json", {"parseTableId": "table_0000", "tables": []})
    write_json(
        table / "summary.json",
        {"title": "Example", "classification": "vector table", "pages": [1],
         "bboxes": [[0, 0, 1, 1]], "surroundingText": {"before": "", "after": ""},
         "imageTable": False, "skipped": False, "skipReason": "", "strategy": "",
         "sqlFriendly": True, "extractionDpi": 216, "steps": []},
    )
    write_sample(
        table,
        {"mode": "content", "totalRows": 3, "header": ["Name", "Value"],
         "rows": [{"rowIndex": 1, "values": ["Alpha", "1"]},
                  {"rowIndex": 2, "values": ["Beta", "2"]}], "skipReason": ""},
    )
    (table / "parse.py").write_text(PARSER, encoding="utf-8")
    return Context(paths), table


def test_review_accepts_sample_and_matching_csv(tmp_path: Path) -> None:
    context, _ = prepare(tmp_path)
    review = run(context, "table_0000")
    assert review["accepted"] is True
    assert review["status"] == "verified"
    assert review["rowCount"] == 3


def test_review_uses_current_sample_as_deterministic_evidence(tmp_path: Path) -> None:
    context, table = prepare(tmp_path)
    sample = base_sample()
    sample["rows"][0]["values"][0] = "Changed"
    write_sample(table, sample)
    review = run(context, "table_0000")
    assert review["accepted"] is False
    assert any("row 1 mismatch" in error for error in review["errors"])


def test_review_rejects_entirely_empty_data_row(tmp_path: Path) -> None:
    context, table = prepare(tmp_path)
    parser = PARSER.replace('["Beta", "2"]', '["", ""], ["Beta", "2"]')
    (table / "parse.py").write_text(parser, encoding="utf-8")
    review = run(context, "table_0000")
    assert review["accepted"] is False
    assert review["csvProfile"]["emptyDataRowIndexes"] == [2]
    assert any("entirely empty data rows" in error for error in review["errors"])


def test_review_does_not_infer_cross_row_leakage_from_matching_sample(tmp_path: Path) -> None:
    context, table = prepare(tmp_path)
    parser = PARSER.replace('["Alpha", "1"]', '["Alpha ei-", "1"]').replace(
        '["Beta", "2"]', '["nes Beta", "2"]'
    )
    (table / "parse.py").write_text(parser, encoding="utf-8")
    sample = base_sample()
    sample["rows"][0]["values"][0] = "Alpha ei-"
    sample["rows"][1]["values"][0] = "nes Beta"
    write_sample(table, sample)
    review = run(context, "table_0000")
    assert review["accepted"] is True

def test_review_accepts_legitimate_repeated_next_row_prefix(tmp_path: Path) -> None:
    context, table = prepare(tmp_path)
    parser = PARSER.replace('["Alpha", "1"]', '["Sammler Alpha Sammler", "1"]').replace(
        '["Beta", "2"]', '["Sammler Beta", "2"]'
    )
    (table / "parse.py").write_text(parser, encoding="utf-8")
    sample = base_sample()
    sample["rows"][0]["values"][0] = "Sammler Alpha Sammler"
    sample["rows"][1]["values"][0] = "Sammler Beta"
    write_sample(table, sample)
    review = run(context, "table_0000")
    assert review["accepted"] is True


def test_review_rejects_sample_row_with_wrong_width(tmp_path: Path) -> None:
    context, table = prepare(tmp_path)
    sample = base_sample()
    sample["rows"][0]["values"] = ["Alpha"]
    write_sample(table, sample)
    review = run(context, "table_0000")
    assert review["accepted"] is False
    assert any("has 1 cells; expected 2" in error for error in review["errors"])


def test_review_rejects_non_object_sample_row_without_crashing(tmp_path: Path) -> None:
    context, table = prepare(tmp_path)
    sample = base_sample()
    sample["rows"] = [["not", "an object"]]
    write_sample(table, sample)
    review = run(context, "table_0000")
    assert review["accepted"] is False
    assert any("sample rows must be" in error for error in review["errors"])


def test_vector_table_cannot_use_truthy_non_boolean_image_flag(tmp_path: Path) -> None:
    context, table = prepare(tmp_path)
    summary = json.loads((table / "summary.json").read_text())
    summary["imageTable"] = {"attachment": 1}
    write_json(table / "summary.json", summary)
    review = run(context, "table_0000")
    assert review["accepted"] is False
    assert any("imageTable must be bool" in error for error in review["errors"])


def test_true_image_table_can_be_format_only(tmp_path: Path) -> None:
    context, table = prepare(tmp_path)
    summary = json.loads((table / "summary.json").read_text())
    summary["imageTable"] = True
    write_json(table / "summary.json", summary)
    write_sample(table, {"mode": "skip", "totalRows": 0, "header": [], "rows": [],
                         "skipReason": "image-only table"})
    review = run(context, "table_0000")
    assert review["accepted"] is True
    assert review["status"] == "format_only"


def test_current_ignores_natural_language_strategy_name(tmp_path: Path) -> None:
    context, table = prepare(tmp_path)
    summary = json.loads((table / "summary.json").read_text())
    summary["strategy"] = "self-contained recursive geometry parser that accepts embedded words"
    write_json(table / "summary.json", summary)
    assert current(context, "table_0000")["strategyFileName"] == ""


def test_review_accepts_declared_hyphen_equivalence(tmp_path: Path) -> None:
    context, table = prepare(tmp_path)
    sample = base_sample()
    sample["rows"][0]["values"][0] = "Al-pha"
    sample["compareRules"] = [{"kind": "ignore_space_hyphen", "columns": [0]}]
    write_sample(table, sample)
    review = run(context, "table_0000")
    assert review["accepted"] is True
    assert review["hyphenEquivalentMatches"] == [
        {"rowIndex": 1, "columnIndex": 0, "expected": "Al-pha", "actual": "Alpha",
         "rule": "ignore_space_hyphen"}
    ]


def test_review_accepts_only_spacing_around_existing_hyphen(tmp_path: Path) -> None:
    context, table = prepare(tmp_path)
    sample = base_sample()
    sample["rows"][0]["values"][0] = "2040 - 2042"
    write_sample(table, sample)
    parser = table / "parse.py"
    parser.write_text(parser.read_text().replace("Alpha", "2040 -2042"), encoding="utf-8")

    review = run(context, "table_0000")

    assert review["accepted"] is True
    assert review["hyphenEquivalentMatches"][0]["rule"] == "ignore_space_hyphen"


def test_hyphen_rule_does_not_hide_other_content_change(tmp_path: Path) -> None:
    context, table = prepare(tmp_path)
    sample = base_sample()
    sample["rows"][0]["values"][0] = "Al-phabet"
    sample["compareRules"] = [{"kind": "ignore_space_hyphen", "columns": [0]}]
    write_sample(table, sample)
    review = run(context, "table_0000")
    assert review["accepted"] is False
    assert any("row 1 mismatch" in error for error in review["errors"])


def test_hyphen_rule_requires_column_scope(tmp_path: Path) -> None:
    context, table = prepare(tmp_path)
    sample = base_sample()
    sample["compareRules"] = [{"kind": "ignore_space_hyphen"}]
    write_sample(table, sample)
    review = run(context, "table_0000")
    assert review["accepted"] is False
    assert any("columns must be a non-empty array" in error for error in review["errors"])


def base_sample() -> dict:
    return {
        "mode": "content", "totalRows": 3, "header": ["Name", "Value"],
        "rows": [{"rowIndex": 1, "values": ["Alpha", "1"]},
                 {"rowIndex": 2, "values": ["Beta", "2"]}], "skipReason": "",
    }


def write_sample(table: Path, sample: dict) -> None:
    source = "import json\nSAMPLE = " + repr(sample) + "\nprint(json.dumps(SAMPLE, ensure_ascii=False))\n"
    (table / "sample.py").write_text(source, encoding="utf-8")
