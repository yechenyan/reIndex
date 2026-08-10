from __future__ import annotations

from pdf_to_markdown.markdown_tables import find_tables, split_row


def test_split_row_preserves_escaped_pipe_as_cell_text() -> None:
    assert split_row("| a | b \\| c |") == ["a", "b | c"]


def test_find_tables_returns_matrix_without_separator() -> None:
    markdown = "Before\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nAfter\n"
    tables = find_tables(markdown)
    assert len(tables) == 1
    assert tables[0]["matrix"] == [["A", "B"], ["1", "2"]]
    assert markdown[tables[0]["start"] : tables[0]["end"]].startswith("| A")


def test_malformed_table_is_not_accepted() -> None:
    assert find_tables("| A | B |\n| not a separator |\n") == []
