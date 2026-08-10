from __future__ import annotations

from pdf_to_markdown.replacement import apply_replacements


def test_replacement_inserts_once_and_removes_continuation() -> None:
    document = "before OLD-A middle OLD-B after"
    replacement = {
        "replacementId": "specialist_0001",
        "spans": [[7, 12], [20, 25]],
        "replacementMarkdown": "| A |\n|---|\n| 1 |",
    }
    result = apply_replacements(document, [replacement])
    assert result.count("|---|") == 1
    assert "OLD-A" not in result and "OLD-B" not in result
    assert "pdf-to-markdown:specialist_0001" not in result


def test_replacement_rejects_duplicate_runtime_marker() -> None:
    document = "<!-- pdf-to-markdown:specialist_0001:start --> OLD"
    old_start = document.index("OLD")
    replacement = {
        "replacementId": "specialist_0001",
        "spans": [[old_start, old_start + 3]],
        "replacementMarkdown": "| A |\n|---|\n| 1 |",
    }
    try:
        apply_replacements(document, [replacement])
    except ValueError as exc:
        assert "not inserted exactly once" in str(exc)
    else:
        raise AssertionError("duplicate replacement marker was accepted")
