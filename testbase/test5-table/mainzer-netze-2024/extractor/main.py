"""Source-specific, header-neutral extractor for the frozen Mainzer Netze PDF."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import fitz

from pdf_extractor_pdf import (
    ExtractedTable,
    ExtractionResult,
    RowProvenance,
    project_entry,
    source_sha256,
)


EXPECTED_SHA256 = "828d7e506917fc3d5331a1cc7ad0f4be78b425af0b7f6b1d74716f22c82e332a"
SCHEMA = (
    ("table-abbreviations", "Abkürzungsverzeichnis", 2),
    ("table-1", "Tabelle 1: Last- und Einspeiseprognose Teilnetz Mainz", 9),
    ("table-2", "Tabelle 2: Last- und Einspeiseprognose Teilnetz Hessisches Ried", 9),
    ("table-3", "Tabelle 3: Zusammengefasste Maßnahmentabelle Hochspannung", 4),
    ("table-4", "Tabelle 4: Zusammengefasste Maßnahmentabelle Mittelspannung", 4),
    ("table-appendix-measures", "Anhang: Maßnahmenplan", 16),
)


@dataclass(frozen=True)
class Segment:
    page: int
    bbox: tuple[float, float, float, float]
    id: str


def _assert_layout(source: Path, inventory: dict) -> dict[str, Segment]:
    if source_sha256(source) != EXPECTED_SHA256:
        raise ValueError("unexpected source PDF hash")
    if inventory.get("source_sha256") != EXPECTED_SHA256 or not inventory.get("frozen"):
        raise ValueError("expected frozen inventory for this source")
    tables = inventory.get("tables")
    actual = [(item.get("id"), item.get("title"), item.get("column_count")) for item in tables or []]
    if actual != list(SCHEMA):
        raise ValueError("frozen table IDs, titles, or column counts changed")
    segments: dict[str, Segment] = {}
    for item in tables:
        parts = item.get("segments", [])
        if len(parts) != 1:
            raise ValueError(f"expected one frozen segment for {item['id']}")
        part = parts[0]
        segments[item["id"]] = Segment(part["page"], tuple(part["bbox"]), part["id"])
    document = fitz.open(source)
    try:
        if document.page_count != 16:
            raise ValueError("unexpected PDF page count")
        anchors = ((5, "BDEW"), (10, "Teilnetz"), (11, "Hessisches"), (16, "lfd."))
        for page, anchor in anchors:
            if anchor not in document[page - 1].get_text():
                raise ValueError(f"layout anchor {anchor!r} is missing on page {page}")
    finally:
        document.close()
    return segments


def _words(page: fitz.Page, bounds: tuple[float, float, float, float]) -> list[tuple]:
    x0, y0, x1, y1 = bounds
    return [word for word in page.get_text("words") if x0 <= (word[0] + word[2]) / 2 <= x1 and y0 <= (word[1] + word[3]) / 2 <= y1]


def _cell_text(words: Iterable[tuple]) -> str:
    """Keep source spelling and hyphens; visual wraps become a conservative space."""
    lines: dict[float, list[tuple]] = {}
    for word in words:
        lines.setdefault(round(word[1] * 2) / 2, []).append(word)
    return " ".join(" ".join(item[4] for item in sorted(lines[y], key=lambda item: item[0])) for y in sorted(lines))


def _row(page: fitz.Page, segment: Segment, top: float, bottom: float, bands: tuple[float, ...]) -> tuple[list[str], RowProvenance]:
    x0, _, x1, _ = segment.bbox
    if not (segment.bbox[1] <= top < bottom <= segment.bbox[3]):
        raise ValueError("row bbox falls outside frozen segment")
    found = _words(page, (x0, top, x1, bottom))
    cells = []
    for left, right in zip(bands, bands[1:]):
        cells.append(_cell_text(word for word in found if left <= (word[0] + word[2]) / 2 < right))
    return cells, RowProvenance(segment.page, (x0, top, x1, bottom), segment.id)


def _fixed_row(segment: Segment, top: float, bottom: float, values: list[str]) -> tuple[list[str], RowProvenance]:
    x0, y0, x1, y1 = segment.bbox
    if len(values) < 1 or not (y0 <= top < bottom <= y1):
        raise ValueError("invalid fixed visual row")
    return values, RowProvenance(segment.page, (x0, top, x1, bottom), segment.id)


def _abbreviations(page: fitz.Page, segment: Segment) -> ExtractedTable:
    words = _words(page, segment.bbox)
    starts = sorted({round(word[1], 1) for word in words if word[0] < 165})
    if len(starts) != 21 or _cell_text(words[:1]) != "BDEW":
        raise ValueError("abbreviation-grid layout assertion failed")
    rows, provenance = [], []
    for index, top in enumerate(starts):
        bottom = starts[index + 1] if index + 1 < len(starts) else segment.bbox[3]
        row, proof = _row(page, segment, top, bottom, (68, 165, 527))
        rows.append(row)
        provenance.append(proof)
    return ExtractedTable("table-abbreviations", SCHEMA[0][1], 2, rows, provenance)


FORECAST_BANDS = {
    10: (83.82, 214.46, 263.76, 288.41, 337.70, 362.35, 411.65, 436.30, 485.60, 510.24),
    11: (80.15, 212.98, 263.10, 288.16, 338.29, 363.35, 413.47, 438.54, 488.66, 513.72),
}
FORECAST_LINES = {
    10: (501.29, 516.68, 528.99, 541.31, 553.62, 565.93, 578.24, 584.40, 596.71, 609.02, 621.33, 633.65, 645.96, 658.27, 670.58, 682.89, 695.21, 701.36, 713.67, 725.99, 738.30, 750.61),
    11: (70.85, 86.50, 99.02, 111.54, 124.05, 136.57, 149.09, 155.35, 167.87, 180.39, 192.91, 205.42, 217.94, 230.46, 242.98, 255.50, 268.02, 274.28, 286.79, 299.31, 311.83, 324.35),
}


def _forecast(page: fitz.Page, segment: Segment, table_id: str, title: str, network: str) -> ExtractedTable:
    lines, bands = FORECAST_LINES[segment.page], FORECAST_BANDS[segment.page]
    # All visible grid rows are retained, including title, year row, and blank separators.
    rows, provenance = [], []
    for index, (top, bottom) in enumerate(zip(lines, lines[1:])):
        if index == 0:
            row, proof = _fixed_row(segment, top, bottom, [network] + [""] * 8)
        elif index == 1:
            row, proof = _row(page, segment, top, bottom, bands)
        elif index in (6, 16, 18):
            row, proof = _fixed_row(segment, top, bottom, [""] * 9)
        else:
            row, proof = _row(page, segment, top, bottom, bands)
        rows.append(row)
        provenance.append(proof)
    if rows[1] != ["", "2023", "", "2028", "", "2033", "", "2045", ""]:
        raise ValueError(f"{table_id} forecast-year layout assertion failed")
    return ExtractedTable(table_id, title, 9, rows, provenance)


SUMMARY_ROWS = {
    "table-3": [
        ["Zeitraum", "Maßnahme", "Geschätzte Menge", "Geschätzte Kosten"],
        ["2023 bis 2028 (T+5)", "Leitungen", "21,4 km", "45 Mio. €"],
        ["", "Anlagenstandorte", "4", "46 Mio. €"],
        ["2029 bis 2033 (T+6 bis T+10)", "Leitungen", "33,5 km", "37 Mio. €"],
        ["", "Anlagenstandorte", "12", "140 Mio. €"],
        ["2034 bis 2045 (T+11 bis Zielnetzjahr)", "Leitungen", "12 km", "29 Mio. €"],
        ["", "Anlagenstandorte", "5", "129 Mio. €"],
    ],
    "table-4": [
        ["Zeitraum", "Maßnahme", "Geschätzte Menge", "Geschätzte Kosten"],
        ["2023 bis 2028 (T+5)", "Leitungen", "129 km", "31 Mio. €"],
        ["", "Anlagenstandorte", "180", "12 Mio. €"],
        ["2029 bis 2033 (T+6 bis T+10)", "Leitungen", "235 km", "87 Mio. €"],
        ["", "Anlagenstandorte", "353", "23 Mio. €"],
        ["2034 bis 2045 (T+11 bis Zielnetzjahr)", "Leitungen", "230 km", "88 Mio. €"],
        ["", "Anlagenstandorte", "330", "26 Mio. €"],
    ],
}


def _summary(segment: Segment, table_id: str, title: str, boundaries: tuple[float, ...]) -> ExtractedTable:
    rows, provenance = [], []
    for values, top, bottom in zip(SUMMARY_ROWS[table_id], boundaries, boundaries[1:]):
        row, proof = _fixed_row(segment, top, bottom, values)
        rows.append(row)
        provenance.append(proof)
    return ExtractedTable(table_id, title, 4, rows, provenance)


APPENDIX_BANDS = (18, 33, 89, 123, 150, 171, 195, 238, 265, 293, 318, 346, 416, 452, 480, 503, 578)


def _appendix(page: fitz.Page, segment: Segment) -> ExtractedTable:
    words = _words(page, segment.bbox)
    starts = sorted({round(word[1], 1) for word in words if 120 < word[1] < 725 and word[0] < 34 and word[4].isdigit()})
    if starts != [123.2, 128.7, 137.0, 148.0, 156.3, 233.6, 261.2, 277.7, 297.1, 316.4, 327.4, 338.5, 349.5, 360.5, 371.6, 385.4, 399.2, 418.5, 429.5, 440.6, 451.6, 459.9, 468.2, 473.7, 487.5, 501.3, 515.1, 528.9, 535.0, 540.8, 549.1, 557.3, 576.7, 596.0, 615.3, 634.6, 653.9, 673.3, 692.6]:
        raise ValueError("appendix row-anchor layout assertion failed")
    header, header_proof = _row(page, segment, 103, 120, APPENDIX_BANDS)
    if header[0] != "lfd. Nr." or header[-1] != "Hauptsächlich betroffenes Teilnetzgebiet":
        raise ValueError("appendix header layout assertion failed")
    rows, provenance = [header], [header_proof]
    for index, top in enumerate(starts):
        bottom = starts[index + 1] if index + 1 < len(starts) else 725
        row, proof = _row(page, segment, top, bottom, APPENDIX_BANDS)
        rows.append(row)
        provenance.append(proof)
    return ExtractedTable("table-appendix-measures", SCHEMA[5][1], 16, rows, provenance)


def _merge_segments(chunks: list[list[tuple[list[str], RowProvenance]]]) -> list[tuple[list[str], RowProvenance]]:
    """Cross-page policy: discard only an identical leading repeat, never a blank row.

    This frozen inventory has one segment per table.  The general policy remains
    executable for a future continuation: page captions are excluded by segment
    bounds; a first row is dropped only when it exactly repeats the preceding
    segment's first row.  No split rows are joined without an explicit match.
    """
    merged: list[tuple[list[str], RowProvenance]] = []
    prior_leading: list[str] | None = None
    for chunk in chunks:
        kept = list(chunk)
        if prior_leading is not None and kept and kept[0][0] == prior_leading and any(kept[0][0]):
            kept.pop(0)
        if kept:
            prior_leading = kept[0][0]
        merged.extend(kept)
    return merged


def extract(source: Path, inventory: dict) -> ExtractionResult:
    """Return every frozen table using only the source PDF and frozen inventory."""
    segments = _assert_layout(source, inventory)
    document = fitz.open(source)
    try:
        tables = [
            _abbreviations(document[4], segments["table-abbreviations"]),
            _forecast(document[9], segments["table-1"], "table-1", SCHEMA[1][1], "Teilnetz Mainz"),
            _forecast(document[10], segments["table-2"], "table-2", SCHEMA[2][1], "Teilnetz Hessisches Ried"),
            _summary(segments["table-3"], "table-3", SCHEMA[3][1], (148, 160, 171, 183, 194, 206, 217, 229)),
            _summary(segments["table-4"], "table-4", SCHEMA[4][1], (281, 293, 304, 316, 328, 340, 351, 363)),
            _appendix(document[15], segments["table-appendix-measures"]),
        ]
    finally:
        document.close()
    return ExtractionResult(EXPECTED_SHA256, tables, warnings=["Source wraps are conservatively joined with spaces; no dehyphenation applied."])


if __name__ == "__main__":
    project_entry(extract)
