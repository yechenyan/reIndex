from pathlib import Path

from pdf_parse.table_review import compare_sample, execute_review, validate_sample, validate_table


def sample(values, physical=1, total=1):
    return {
        "mode": "sample",
        "rows": [{"physicalRow": physical, "values": values}],
        "totalPhysicalRows": total,
        "compareRules": [],
        "skipReason": "",
    }


def test_table_validation_collects_empty_and_ragged_errors():
    errors = validate_table({"rows": [[""], {"bad": True}]})
    assert "Data row 1 is entirely empty" in errors
    assert "Data row 2 is not an array" in errors


def test_first_visible_row_is_physical_row_one():
    table = {"rows": [["Name", "Value"], ["A", 1]]}
    visual = {
        "mode": "sample",
        "rows": [
            {"physicalRow": 1, "values": ["Name", "Value"]},
            {"physicalRow": 2, "values": ["A", "1"]},
        ],
        "totalPhysicalRows": 2,
        "compareRules": [],
        "skipReason": "",
    }
    assert validate_sample(visual) == []
    assert compare_sample(visual, table) == []


def test_sample_rules_must_be_empty():
    visual = sample(["A"])
    visual["compareRules"] = [{"type": "numeric", "columns": [0]}]
    assert validate_sample(visual) == [
        "Sample compareRules must be an empty array; all cells use LCS"
    ]


def test_text_cells_accept_at_least_eighty_percent_lcs_similarity():
    assert compare_sample(sample(["Musterstad"]), {"rows": [["Musterstadt"]]}) == []


def test_symmetric_lcs_detects_visual_sample_suffix_conflict():
    errors = compare_sample(sample(["Umspannung"]), {"rows": [["Umspannung MS/NS"]]})
    assert errors == [
        "Physical row 1 column 1 LCS=62.5% below 80%; "
        "sample='Umspannung' parser='Umspannung MS/NS'"
    ]


def test_review_reports_exact_failed_physical_cell():
    errors = compare_sample(sample(["Alpha", "Stable"]), {"rows": [["Omega", "Stable"]]})
    assert errors == [
        "Physical row 1 column 1 LCS=20.0% below 80%; sample='Alpha' parser='Omega'"
    ]


def test_review_collects_both_script_syntax_errors(tmp_path: Path):
    (tmp_path / "parse.py").write_text("if True print('x')", encoding="utf-8")
    (tmp_path / "sample.py").write_text("else:\n    pass", encoding="utf-8")
    review = execute_review(tmp_path)
    assert review["status"] == "failed"
    assert len(review["errors"]) == 2
    assert review["errors"][0].startswith("parse.py syntax error:")
    assert review["errors"][1].startswith("sample.py syntax error:")
