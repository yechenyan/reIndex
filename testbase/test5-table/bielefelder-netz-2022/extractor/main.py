"""Extractor for the six displayed-coordinate tables on rotated PDF page 5."""
from __future__ import annotations

from pathlib import Path

import fitz

from pdf_extractor_pdf import (
    ExtractedTable,
    ExtractionResult,
    RowProvenance,
    project_entry,
    source_sha256,
)


SOURCE_SHA256 = "3dc36a9917ac29b387c8fcc6e1a856f26e4fc0660d4e847a5070ee7dca0af497"
LAYOUT = {
    "table-1": ("Optionale Erläuterungen zu Ihren Angaben an die BNetzA", 1, (36, 193, 465, 223)),
    "table-2": ("Teil 1 – Hinweise und Neuerungen zum Vorjahr", 2, (36, 230, 946, 261)),
    "table-3": ("Teil 1 – Aggregierte 10-Jahres-Investitionen mit Übertragungskapazität", 7, (49, 266, 465, 302)),
    "table-4": ("Teil 1 – Aggregierte 10-Jahres-Investitionen ohne Übertragungskapazität", 3, (49, 304, 283, 333)),
    "table-5": ("Teil 2 – Hinweise und Neuerungen zum Vorjahr", 2, (36, 344, 946, 391)),
    "table-6": ("Teil 2 – Maßnahmenplan mit Ausfüllbeispielen und Zellenhinweisen", 20, (36, 398, 1155, 676)),
}
T6_X = (36.26, 48.99, 83.19, 135.27, 283.35, 331.95, 370.95, 419.07,
        465.38, 598.59, 651.98, 699.63, 747.27, 787.11, 829.95, 900.76,
        946.47, 993.99, 1024.83, 1108.95, 1154.45)
T6_Y = (398.40, 403.20, 454.20, 477.24, 479.76, 482.16, 484.56, 486.96,
        489.36, 491.76, 494.16, 496.56, 498.96, 501.36, 503.76, 506.16,
        508.56, 510.96, 513.36, 515.76, 518.16, 520.56, 522.96, 525.36,
        527.76, 530.16, 532.56, 534.96, 539.52, 544.08, 548.64, 553.20,
        557.76, 562.32, 566.88, 571.44, 582.84, 594.24, 598.80, 603.36,
        607.92, 612.48, 617.04, 621.60, 626.16, 630.72, 635.28, 639.84,
        644.40, 648.96, 653.52, 658.08, 662.64, 667.20, 671.76, 676.00)


def extract(source: Path, inventory: dict) -> ExtractionResult:
    """Extract the frozen matrices, converting native coordinates to display space."""
    _assert_layout(source, inventory)
    document = fitz.open(source)
    try:
        page = document[4]
        words = _display_words(page)
        tables = [
            _grid_table(inventory["tables"][0], words, (36.33, 465.45), (193.20, 198.72, 222.72)),
            _notes_table(inventory["tables"][1], words, (230.00, 234.90, 238.80, 244.90, 252.10, 261.00), 465.33),
            _grid_table(inventory["tables"][2], words, (48.99, 83.19, 135.27, 283.35, 331.95, 370.95, 419.07, 465.45), (266.04, 280.38, 287.58, 294.78, 301.92)),
            _grid_table(inventory["tables"][3], words, (48.99, 83.19, 135.27, 283.00), (304.38, 311.58, 318.78, 325.98, 332.90)),
            _notes_table(inventory["tables"][4], words, (344.00, 348.00, 350.90, 355.80, 360.60, 365.20, 369.90, 374.70, 380.10, 385.00, 391.00), 465.33),
            _grid_table(inventory["tables"][5], words, T6_X, T6_Y),
        ]
        return ExtractionResult(source_sha256=SOURCE_SHA256, tables=_only_proven_merges(tables))
    finally:
        document.close()


def _assert_layout(source: Path, inventory: dict) -> None:
    if source_sha256(source) != SOURCE_SHA256 or inventory.get("source_sha256") != SOURCE_SHA256:
        raise ValueError("this extractor is pinned to the frozen Bielefelder source")
    tables = inventory.get("tables")
    if not isinstance(tables, list) or len(tables) != len(LAYOUT):
        raise ValueError("frozen table layout changed")
    for table in tables:
        expected = LAYOUT.get(table.get("id"))
        if not expected or table.get("title") != expected[0] or table.get("column_count") != expected[1]:
            raise ValueError("frozen table schema changed")
        segments = table.get("segments")
        if not isinstance(segments, list) or len(segments) != 1 or segments[0].get("page") != 5:
            raise ValueError("this layout has one page-5 segment per table")
        if tuple(segments[0].get("bbox", ())) != expected[2]:
            raise ValueError("frozen displayed-coordinate bbox changed")
    with fitz.open(source) as document:
        if len(document) != 5 or document[4].rotation != 90 or tuple(document[4].rect) != (0.0, 0.0, 1191.0, 842.0):
            raise ValueError("expected the original 90-degree displayed page 5")


def _display_words(page: fitz.Page) -> list[tuple[fitz.Rect, str]]:
    # PyMuPDF returns this page's word boxes in native media coordinates even
    # though the frozen inventory and rendered segments are in displayed space.
    matrix = page.rotation_matrix
    return [(fitz.Rect(word[:4]) * matrix, str(word[4])) for word in page.get_text("words")]


def _grid_table(table: dict, words: list[tuple[fitz.Rect, str]], xs: tuple[float, ...], ys: tuple[float, ...]) -> ExtractedTable:
    segment = table["segments"][0]
    rows = []
    provenance = []
    for index, (top, bottom) in enumerate(zip(ys, ys[1:])):
        if table["id"] == "table-6" and index == 0:
            # The blue caption is a single merged first row, not two cells.
            cells = [_text_in(words, fitz.Rect(xs[0], top, xs[-1], bottom))] + [""] * (table["column_count"] - 1)
        else:
            cells = [_text_in(words, fitz.Rect(left, top, right, bottom)) for left, right in zip(xs, xs[1:])]
        rows.append(cells)
        provenance.append(_provenance(segment, (xs[0], top, xs[-1], bottom)))
    return ExtractedTable(table["id"], table["title"], table["column_count"], rows, provenance)


def _notes_table(table: dict, words: list[tuple[fitz.Rect, str]], ys: tuple[float, ...], split: float) -> ExtractedTable:
    segment = table["segments"][0]
    x0, _, x1, _ = segment["bbox"]
    rows = []
    provenance = []
    for top, bottom in zip(ys, ys[1:]):
        rows.append([_text_in(words, fitz.Rect(x0, top, split, bottom)), _text_in(words, fitz.Rect(split, top, x1, bottom))])
        provenance.append(_provenance(segment, (x0, top, x1, bottom)))
    return ExtractedTable(table["id"], table["title"], 2, rows, provenance)


def _text_in(words: list[tuple[fitz.Rect, str]], cell: fitz.Rect) -> str:
    selected = [(rect, text) for rect, text in words if cell.contains(rect.tl + (rect.br - rect.tl) * 0.5)]
    lines: list[list[tuple[fitz.Rect, str]]] = []
    for item in sorted(selected, key=lambda value: (value[0].y0, value[0].x0)):
        if not lines or abs(item[0].y0 - lines[-1][0][0].y0) > 1.0:
            lines.append([item])
        else:
            lines[-1].append(item)
    return "\n".join(" ".join(text for _, text in sorted(line, key=lambda value: value[0].x0)) for line in lines)


def _provenance(segment: dict, bbox: tuple[float, float, float, float]) -> RowProvenance:
    sx0, sy0, sx1, sy1 = segment["bbox"]
    x0, y0, x1, y1 = bbox
    clipped = (max(sx0, x0), max(sy0, y0), min(sx1, x1), min(sy1, y1))
    if clipped[0] >= clipped[2] or clipped[1] >= clipped[3]:
        raise ValueError("row bbox escaped its frozen segment")
    return RowProvenance(page=segment["page"], bbox=clipped, segment_id=segment["id"])


def _only_proven_merges(tables: list[ExtractedTable]) -> list[ExtractedTable]:
    """Executable merge policy: all frozen tables are single, non-continuation segments."""
    if any(len(table.provenance) != len(table.rows) for table in tables):
        raise ValueError("merge policy requires row-aligned provenance")
    return tables


if __name__ == "__main__":
    project_entry(extract)
