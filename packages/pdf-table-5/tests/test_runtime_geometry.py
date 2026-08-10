from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdf_table_5.runtime_geometry import WORD_FORMAT, join_word_text, load_segments


def test_runtime_loader_matches_compact_prompt_shape(tmp_path: Path) -> None:
    geometry = tmp_path / "geometry.json"
    geometry.write_text(
        json.dumps({"words": [
            {"bbox": [1.234, 2, 3, 4], "text": "Cell", "block": 1, "line": 2, "word": 3},
            [5, 6, 7, 8, "Array"],
        ]}),
        encoding="utf-8",
    )
    table = tmp_path / "table.json"
    table.write_text(
        json.dumps({"projectRoot": str(tmp_path), "tables": [{"page": 2, "geometry": "geometry.json"}]}),
        encoding="utf-8",
    )
    segments = load_segments(table)
    assert WORD_FORMAT == ("x0", "y0", "x1", "y1", "text", "block", "line", "word")
    assert segments[0]["words"] == [
        [1.23, 2.0, 3.0, 4.0, "Cell", 1, 2, 3],
        [5.0, 6.0, 7.0, 8.0, "Array", 0, 0, 0],
    ]
    assert segments[0]["geometryPath"] == str(geometry)


def test_runtime_loader_rejects_missing_project_root(tmp_path: Path) -> None:
    table = tmp_path / "table.json"
    table.write_text(json.dumps({"tables": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="projectRoot"):
        load_segments(table)


def test_join_word_text_handles_wrap_and_compound_hyphens() -> None:
    words = lambda *values: [[index, y, index + 0.8, y + 1, text, 0, 0, index]
                             for index, (text, y) in enumerate(values)]
    assert join_word_text(words(("Übertra-", 0), ("gungskapazität", 2))) == "Übertragungskapazität"
    assert join_word_text(words(("MS-", 0), ("Kabel", 0))) == "MS-Kabel"
    assert join_word_text(words(("Schutz-", 0), ("und", 0))) == "Schutz- und"
    assert join_word_text(words(("Schutz-", 0), ("&", 0))) == "Schutz- &"
    assert join_word_text(words(("Netzoptimie-", 0), ("rung", 2), ("und", 2),
                                ("-ver-", 2), ("stärkung", 4))) == (
        "Netzoptimierung und -verstärkung"
    )
    assert join_word_text(words(("-", 0))) == "-"
