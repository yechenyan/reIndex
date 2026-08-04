"""Geometry-driven extractor for the E.DIS Netzausbauplan 2024.

The report's small tables are conventional horizontal grids.  The annex is a
landscape table whose PDF text is stored as vertical record strips; it is
therefore extracted separately rather than trusting reading order.
"""
from __future__ import annotations

import json
from pathlib import Path

from pdf_extractor_pdf import (
    ExtractedTable,
    ExtractionResult,
    RowProvenance,
    project_entry,
    source_sha256,
)


ROOT = Path(__file__).resolve().parent


def _geometry(table_id: str, segment_id: str) -> dict:
    files = sorted((ROOT / "evidence" / "segments" / table_id).glob(f"{segment_id}-*.json"))
    if len(files) != 1:
        raise RuntimeError(f"missing or ambiguous geometry for {table_id}/{segment_id}")
    return json.loads(files[0].read_text(encoding="utf-8"))


def _words_in_cell(words: list[list], x0: float, x1: float, y0: float, y1: float) -> list[list]:
    # Midpoints avoid assigning a glyph that touches a rule to both cells.
    selected = [w for w in words if x0 <= (w[0] + w[2]) / 2 < x1 and y0 <= (w[1] + w[3]) / 2 < y1]
    return sorted(selected, key=lambda w: (round(w[1], 1), w[0], w[7]))


def _text(words: list[list]) -> str:
    """Preserve visible German text while collapsing PDF extraction spacing."""
    if not words:
        return ""
    lines: list[list[list]] = []
    for word in words:
        if not lines or abs(word[1] - lines[-1][0][1]) > 2.2:
            lines.append([word])
        else:
            lines[-1].append(word)
    return " ".join(" ".join(w[4] for w in line) for line in lines).replace("\u00ad", "")


def _rotated_text(words: list[list]) -> str:
    """Read one annex strip from its visual bottom back toward its top."""
    return " ".join(w[4] for w in sorted(words, key=lambda w: (-round(w[1], 1), w[0], w[7]))).replace("\u00ad", "")


def _bbox(words: list[list], fallback: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    if not words:
        return fallback
    return (min(w[0] for w in words), min(w[1] for w in words), max(w[2] for w in words), max(w[3] for w in words))


def _grid(table: dict, columns: list[str], x_edges: list[float], y_centres: list[float],
          window: float = 5.5) -> ExtractedTable:
    segment = table["segments"][0]
    geo = _geometry(table["id"], segment["id"])
    words = geo["words"]
    rows: list[list[str]] = []
    provenance: list[RowProvenance] = []
    for y in y_centres:
        # Neighbouring body rows are 15--18pt apart.  The broader tolerance
        # retains labels deliberately baseline-shifted relative to numbers.
        row_words = [w for w in words if abs(((w[1] + w[3]) / 2) - y) <= window]
        values = [_text(_words_in_cell(row_words, x_edges[i], x_edges[i + 1], y - window, y + window))
                  for i in range(len(columns))]
        rows.append(values)
        provenance.append(RowProvenance(geo["page"], _bbox(row_words, tuple(segment["bbox"])), segment["id"]))
    return ExtractedTable(table["id"], table["title"], columns, rows, provenance)


def _annex(table: dict) -> ExtractedTable:
    columns = [
        "lfd. Nr.", "Maßnahme", "kurze Projektbeschreibung", "Projektkategorie", "Betriebsmittel",
        "Länge des zugebauten, optimierten oder ersetzten Leitungsabschnitts",
        "Änderung der Übertragungskapazität", "netztechnische Begründung für den Netzausbau (Kurzbeschreibung)",
        "netztechnische Begründung für den Netzausbau (Grund)",
        "Erfolgt diese Netzausbaumaßnahme, um einen bereits bestehenden Engpass zu beheben?",
        "Erfolgt diese Netzausbaumaßnahme, um einen prognostizierten Engpass vorzubeugen?",
        "benötigt bis", "voraussichtlicher Zeitpunkt des Baubeginns",
        "voraussichtlicher Zeitpunkt der Inbetriebnahme", "geschätzte Kosten",
        "Projektstatus", "Teilnetzgebiet",
    ]
    y_edges = [55, 105, 160, 195, 230, 263, 287, 360, 433, 520, 650, 686, 744, 782, 842]
    rows: list[list[str]] = []
    provenance: list[RowProvenance] = []
    # The rotated source uses a fixed 12.54pt strip pitch.  Territory markers
    # are sometimes empty/form-field text, so using them as the row detector
    # loses two genuine source records.  The geometry itself establishes 57
    # strips on pages 25--33 and 52 on the final page.
    strip_pitch = 12.54
    first_centre = 86.6073
    for segment_index, segment in enumerate(table["segments"]):
        geo = _geometry(table["id"], segment["id"])
        strip_count = 52 if segment_index == len(table["segments"]) - 1 else 57
        for strip_index in range(strip_count):
            centre = first_centre + strip_index * strip_pitch
            # Adjacent record strips are 12.5pt wide.  This interval also
            # excludes the fixed, repeated vertical heading column.
            record_words = [w for w in geo["words"] if centre - 6.3 <= (w[0] + w[2]) / 2 < centre + 6.3]
            physical = [_rotated_text(_words_in_cell(record_words, centre - 6.3, centre + 6.3,
                                                       y_edges[i], y_edges[i + 1]))
                        for i in range(len(y_edges) - 1)]
            # The source's logical left-to-right sequence is the reverse of
            # the rotated y-axis.  Its running number follows the physically
            # ordered strip sequence (the first annex record is source no. 7).
            values = [str(7 + len(rows)), "", "", physical[13], physical[12], physical[11], physical[10],
                      physical[9], physical[8], physical[7], physical[6], physical[5],
                      physical[4], physical[3], physical[2], physical[1], physical[0]]
            rows.append(values)
            provenance.append(RowProvenance(geo["page"], _bbox(record_words, tuple(segment["bbox"])), segment["id"]))
    return ExtractedTable(table["id"], table["title"], columns, rows, provenance)


def _merge_period_pairs(table: ExtractedTable) -> ExtractedTable:
    """Represent a vertically merged Zeitraum cell once, on its first row."""
    rows = [row[:] for row in table.rows]
    for first in range(0, len(rows), 2):
        second = first + 1
        if second >= len(rows):
            break
        rows[first][0] = " ".join(value for value in (rows[first][0], rows[second][0]) if value)
        rows[second][0] = ""
    return ExtractedTable(table.id, table.title, table.columns, rows, table.provenance)


def _attach_single_row_periods(table: ExtractedTable, x0: float, x1: float,
                               y_centres: list[float]) -> ExtractedTable:
    """Capture both baselines of a one-row Zeitraum cell (date and suffix)."""
    segment = {"id": table.provenance[0].segment_id}
    geo = _geometry(table.id, segment["id"])
    rows = [row[:] for row in table.rows]
    for index, y in enumerate(y_centres):
        period_words = _words_in_cell(geo["words"], x0, x1, y - 15, y + 15)
        rows[index][0] = _text(period_words)
    return ExtractedTable(table.id, table.title, table.columns, rows, table.provenance)


def _table_11_hyphenation(table: ExtractedTable) -> ExtractedTable:
    rows = [row[:] for row in table.rows]
    for row in rows:
        if row[0].strip() == "Mecklenburg-":
            row[0] = "Mecklenburg-Vorpommern"
        else:
            row[0] = row[0].replace("Mecklenburg- Vorpommern", "Mecklenburg-Vorpommern")
    return ExtractedTable(table.id, table.title, table.columns, rows, table.provenance)


def extract(source: Path, inventory: dict) -> ExtractionResult:
    """Return every frozen table in inventory order with per-row provenance."""
    by_id = {table["id"]: table for table in inventory["tables"]}
    specs = {
        "table-01": (["Zeitraum", "Einheit", "2023", "2028", "2033", "2045"], [68, 180, 285, 350, 412, 474, 525], [240, 257, 275, 292, 312, 329, 347, 364]),
        "table-02": (["Zeitraum", "Einheit", "2023", "2028", "2033", "2045"], [68, 180, 285, 350, 412, 474, 525], [433, 451, 468, 486, 505, 523, 540, 558]),
        "table-03": (["Teilnetzgebiet", "2028", "2033", "2045"], [68, 230, 330, 425, 498], [182, 200]),
        "table-04": (["Netzebene", "2023", "2028", "2033", "2045"], [68, 190, 270, 350, 430, 498], [514, 531, 549, 566, 584]),
        "table-05": (["Netzebene", "2023", "2028", "2033", "2045"], [68, 190, 270, 350, 430, 500], [655, 672, 689, 707, 724]),
        "table-06": (["Netzebene", "2023", "2028", "2033", "2045"], [68, 190, 270, 350, 430, 498], [139, 156, 174, 191, 209]),
        "table-07": (["Netzebene", "2023", "2028", "2033", "2045"], [68, 190, 270, 350, 430, 498], [280, 297, 314, 332, 349]),
        "table-08": (["Zeitraum", "Maßnahme", "Geschätzte Menge", "Geschätzte Kosten"], [68, 180, 290, 400, 520], [644, 661, 679, 696, 714, 731]),
        "table-09": (["Zeitraum", "Maßnahme", "Geschätzte Menge", "Geschätzte Kosten"], [66, 180, 290, 400, 522], [153, 171, 188, 206, 223, 241]),
        "table-10": (["Zeitraum", "Ausbau", "Neubau"], [68, 270, 420, 520], [672, 690, 707]),
        "table-11": (["Teilnetzgebiet", "überlastete Leitungen", "überlastete Ortsnetzstationen", "Auslöser Last", "Auslöser Einspeisung"], [68, 150, 255, 345, 420, 498], [695, 720]),
        "table-12": (["Zeitraum", "Maßnahme", "geschätzte Menge", "geschätzte Kosten"], [68, 180, 290, 400, 520], [211, 229, 246, 264, 281, 299]),
        "table-13": (["Zeitraum", "Maßnahme", "geschätzte Menge", "geschätzte Kosten"], [68, 180, 290, 400, 520], [377, 394, 412, 429, 447, 464]),
        "table-14": (["Zeitraum", "Maßnahme", "geschätzte Menge", "geschätzte Kosten"], [68, 180, 290, 400, 520], [264, 299, 333]),
        "table-15": (["Zeitraum", "Maßnahme", "geschätzte Menge", "geschätzte Kosten"], [68, 180, 290, 400, 520], [428, 463, 498]),
    }
    # The affected source tables place labels up to about 6.5pt below their
    # numeric baseline.  Keep table-02/03 on the original narrow window:
    # they are outside the repair scope and their output is intentionally fixed.
    tables = [
        _grid(by_id[table_id], *specs[table_id], window=8.5 if table_id not in {"table-02", "table-03"} else 5.5)
        for table_id in (f"table-{i:02d}" for i in range(1, 16))
    ]
    # 08/09 and the two MS tables have one Zeitraum cell spanning each two
    # measure rows.  Do not repeat its parenthetical suffix on the second row.
    for index in (7, 8, 11, 12):
        tables[index] = _merge_period_pairs(tables[index])
    tables[10] = _table_11_hyphenation(tables[10])
    # NS has one measure per period, but the date and parenthetical suffix use
    # separate baselines within that same cell.
    tables[13] = _attach_single_row_periods(tables[13], 68, 180, [264, 299, 333])
    tables[14] = _attach_single_row_periods(tables[14], 68, 180, [428, 463, 498])
    tables.append(_annex(by_id["table-16"]))
    return ExtractionResult(source_sha256(source), tables, extractor_version="geometry-1.0")


if __name__ == "__main__":
    project_entry(extract)
