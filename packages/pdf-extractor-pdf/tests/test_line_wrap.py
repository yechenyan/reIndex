from __future__ import annotations

from pdf_extractor_pdf.line_wrap import (
    _geometry_candidates,
    apply_result,
    classify_line_wrap_candidate,
    normalize_visual_line_wrap,
    validate_decisions,
)


def test_geometry_finds_only_visual_line_end_hyphens() -> None:
    segment = {"table_id": "t", "segment_id": "s", "page": 1, "image": "segment.png"}
    geometry = {"words": [
        [0, 0, 40, 10, "Zusammenfas-", 1, 0, 0],
        [-20, 12, -10, 22, "sen", 1, 1, 0],
        [12, 12, 30, 22, "MS-Kabel", 1, 1, 1],
        [50, 0, 70, 10, "N-1", 2, 0, 0],
    ]}
    values = _geometry_candidates(segment, geometry)
    assert [(x["line_end"], x["next_line_start"]) for x in values] == [("Zusammenfas-", "sen")]


def test_geometry_follows_wrapped_cell_across_pdf_blocks() -> None:
    segment = {"table_id": "t", "segment_id": "s", "page": 1, "image": "segment.png"}
    geometry = {"words": [
        [20, 0, 60, 10, "Projektkatego-", 1, 0, 0],
        [35, 12, 45, 22, "rie", 2, 0, 0],
        [80, 12, 100, 22, "other", 3, 0, 0],
    ]}
    values = _geometry_candidates(segment, geometry)
    assert [(x["line_end"], x["next_line_start"]) for x in values] == [("Projektkatego-", "rie")]


def test_qa_remove_decision_normalizes_all_matching_cells() -> None:
    decision = {
        "id": "wrap-placeholder", "line_end": "Übertra-", "next_line_start": "gungskapazität",
        "decision": "remove", "decision_source": "code", "occurrences": [],
    }
    from pdf_extractor_pdf.line_wrap import _candidate_id
    decision["id"] = _candidate_id("t", decision["line_end"], decision["next_line_start"])
    validate_decisions([decision], "t")
    reference = {"tables": [{"id": "t", "line_wrap_decisions": [decision]}]}
    result = {"tables": [{
        "id": "t", "column_count": 1,
        "rows": [["Übertra- gungskapazität"], ["soft\u00adhyphen"]], "provenance": [{}, {}],
    }]}
    normalized = apply_result(reference, result)["tables"][0]
    assert normalized["rows"] == [["Übertragungskapazität"], ["softhyphen"]]


def test_qa_keep_decision_removes_visual_space_but_keeps_hyphen() -> None:
    from pdf_extractor_pdf.line_wrap import _candidate_id
    decision = {
        "id": _candidate_id("t", "MS-", "Kabel"), "line_end": "MS-",
        "next_line_start": "Kabel", "decision": "keep", "decision_source": "code", "occurrences": [],
    }
    reference = {"tables": [{"id": "t", "line_wrap_decisions": [decision]}]}
    result = {"tables": [{"id": "t", "column_count": 1, "rows": [["MS- Kabel"]], "provenance": [{}]}]}
    assert apply_result(reference, result)["tables"][0]["rows"] == [["MS-Kabel"]]


def test_simple_line_wrap_classifier_is_language_independent() -> None:
    assert classify_line_wrap_candidate("Zusammenfas-", "sen") == "remove"
    assert classify_line_wrap_candidate("MS-", "Kabel") == "keep"
    assert classify_line_wrap_candidate("Teil-", "2") == "keep"
    assert classify_line_wrap_candidate("Wort-", "(Zusatz)") is None
    assert normalize_visual_line_wrap("soft\u00adhyphen", []) == "softhyphen"
