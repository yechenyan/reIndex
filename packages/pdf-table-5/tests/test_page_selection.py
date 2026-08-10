from __future__ import annotations

import pytest

from pdf_table_5.page_selection import normalize_pages


def test_page_expression_is_sorted_and_deduplicated() -> None:
    assert normalize_pages("5,2-4,3", 8) == [2, 3, 4, 5]


@pytest.mark.parametrize("value", ["", "0", "3-2", "1,,2", "a", "1-2-3"])
def test_invalid_page_expression_fails(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_pages(value, 8)


def test_outside_page_fails() -> None:
    with pytest.raises(ValueError, match="outside"):
        normalize_pages("9", 8)
