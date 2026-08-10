from __future__ import annotations

from pdf_to_markdown.candidates import discover


def page(number: int, markdown: str, runs: int, items=None, vector_lines: int = 0) -> dict:
    return {
        "page": number,
        "width": 300.0,
        "height": 200.0,
        "markdown": markdown,
        "textItems": items or [],
        "vectorLines": [{}] * vector_lines,
        "complexity": {"layout": {"ruled_table_count": int(bool(runs)), "text_table_run_count": runs}},
    }


def item(text: str, x: float, y: float) -> dict:
    return {"text": text, "x": x, "y": y, "width": 20.0, "height": 10.0}


def test_simple_markdown_table_routes_to_sample() -> None:
    markdown = "| A | B |\n|---|---|\n| 1 | 2 |\n"
    items = [item("A", 10, 20), item("B", 50, 20), item("1", 10, 40), item("2", 50, 40)]
    value = {"markdown": markdown, "pages": [page(1, markdown, 1, items)]}
    candidates = discover(value)
    assert candidates[0]["route"] == "sample"
    assert candidates[0]["spans"] == [[0, len(markdown)]]


def test_adjacent_fragmented_pages_remain_page_candidates() -> None:
    first, second = "Text\n| broken\n", "| continued\nCaption\n"
    document = first + "\n-----\n" + second
    value = {"markdown": document, "pages": [page(2, first, 3), page(3, second, 4)]}
    candidates = discover(value)
    assert [candidate["pages"] for candidate in candidates] == [[2], [3]]
    assert all(candidate["route"] == "specialist" for candidate in candidates)


def test_simple_page_between_complex_pages_is_not_absorbed() -> None:
    parts = ["| first | row |\n", "| middle | row |\n", "| last | row |\n"]
    document = "\n-----\n".join(parts)
    value = {
        "markdown": document,
        "pages": [page(15, parts[0], 3), page(16, parts[1], 1), page(17, parts[2], 4)],
    }
    candidates = discover(value)
    assert [candidate["pages"] for candidate in candidates] == [[15], [16], [17]]


def test_dense_vector_grid_routes_to_specialist_without_complexity_signal() -> None:
    markdown = "Header\n| malformed | rows |\n"
    value = {"markdown": markdown, "pages": [page(41, markdown, 0, vector_lines=1122)]}
    candidates = discover(value)
    assert len(candidates) == 1
    assert candidates[0]["pages"] == [41]
    assert candidates[0]["source"] == "page-table-signal"
    assert candidates[0]["route"] == "specialist"
