from __future__ import annotations

from pdf_to_markdown.sample_compare import compare, expected_indexes


def test_expected_indexes_samples_boundaries() -> None:
    assert expected_indexes(5) == [1, 2, 3, 4]
    assert expected_indexes(10) == [1, 2, 3, 7, 8, 9]


def test_compare_checks_source_rows() -> None:
    matrix = [["A", "B"], ["1", "2"], ["3", "4"]]
    sample = {
        "readable": True,
        "reason": "",
        "totalRows": 3,
        "header": ["A", "B"],
        "rows": [{"rowIndex": 1, "values": ["1", "2"]}, {"rowIndex": 2, "values": ["3", "4"]}],
    }
    assert compare(matrix, sample)["passed"] is True
    sample["rows"][1]["values"][1] = "wrong"
    assert compare(matrix, sample)["passed"] is False
