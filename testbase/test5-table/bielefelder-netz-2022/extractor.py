"""Deterministic extractor for the exact Bielefelder Netz 2022 PDF."""

from __future__ import annotations

from pathlib import Path

import fitz

from pdf_table_codegen import (
    CompatibilityReport,
    ExtractedTable,
    ExtractionRequest,
    ExtractionResult,
    QaFinding,
    QaReport,
    RowProvenance,
)
from pdf_table_codegen.models import source_sha256

SOURCE_SHA256 = "3dc36a9917ac29b387c8fcc6e1a856f26e4fc0660d4e847a5070ee7dca0af497"
LEVELS = ["Mittelspannung", "Umspannung MS/NS", "Niederspannung"]
CATEGORIES = [
    "Neubau",
    "Ersatz(neubau) mit Erhöhung der Übertragungskapazität",
    "Netzoptimierung und -verstärkung",
    "Summe Netzausbau",
    "davon überwiegend erzeugungsgetrieben",
    "davon überwiegend verbrauchsbedingt",
    "Ersatz(neubau) ohne Erhöhung der Übertragungskapazität",
    "Rückbau / Altlastentsorgung",
]
DETAIL_HEADERS = [
    "lfd. Nr.", "Maßnahme", "Betroffener Netzknoten im überlagerten HöS-Netz",
    "Kurze Projektbeschreibung", "Projektkategorie", "Betriebsmittel",
    "Länge Leitungsabschnitt [km]", "Änderung Übertragungskapazität [+/- MVA]",
    "Netztechnische Begründung", "Überwiegender Ausbaugrund",
    "Bestehenden Engpass beheben", "Prognostiziertem Engpass vorbeugen",
    "Voraussichtlicher Baubeginn [MM/JJJJ]",
    "Voraussichtliche Inbetriebnahme [MM/JJJJ]", "Verzögerungsgrund",
    "Kosten (geschätzt) in Euro", "Projektstatus", "Stand Genehmigungsverfahren",
    "Geprüfte Alternativen", "Vorrangige Netz- oder Umspannebene",
]
DETAIL_COLUMNS = [
    1154.67, 1141.95, 1107.75, 1055.67, 907.59, 858.99, 819.99, 771.87,
    725.55, 592.35, 538.95, 491.31, 443.67, 403.83, 360.99, 290.19,
    244.47, 196.95, 166.11, 81.99, 36.51,
]
DETAIL_ROWS = [
    477.48, 479.88, 482.28, 484.68, 487.08, 489.48, 491.88, 494.28,
    496.68, 499.08, 501.48, 503.88, 506.28, 508.68, 511.08, 513.48,
    515.88, 518.28, 520.68, 523.08, 525.48, 527.88, 530.28, 532.68,
    535.08, 539.64, 544.20, 548.76, 553.32, 557.88, 562.44, 567.00,
    571.56, 582.96, 594.36, 598.92, 603.48, 608.04, 612.60, 617.16,
    621.72, 626.28, 630.84, 635.40, 639.96, 644.52, 649.08, 653.64,
    658.20, 662.76, 667.32, 671.88, 676.44,
]


def can_handle(source: Path) -> CompatibilityReport:
    digest = source_sha256(source)
    return CompatibilityReport(digest == SOURCE_SHA256, "exact source hash" if digest == SOURCE_SHA256 else "unknown PDF revision", digest)


def _cell(words: list[tuple], x0: float, x1: float, y0: float, y1: float) -> str:
    lo_y, hi_y = sorted((y0, y1))
    selected = [word for word in words if x0 <= (word[0] + word[2]) / 2 < x1 and lo_y <= (word[1] + word[3]) / 2 < hi_y]
    selected.sort(key=lambda word: (round(word[0], 1), -word[1]))
    return " ".join(word[4] for word in selected).strip()


def _grid(words, header_x, row_bounds, columns):
    headers = [_cell(words, *header_x, columns[index + 1], columns[index]) for index in range(2, len(columns) - 1)]
    rows = []
    for x0, x1 in zip(row_bounds, row_bounds[1:]):
        level = _cell(words, x0, x1, columns[2], columns[1])
        values = [_cell(words, x0, x1, columns[index + 1], columns[index]) for index in range(2, len(columns) - 1)]
        rows.append((level, dict(zip(headers, values))))
    return rows


def _category(source: str) -> str:
    prefix = "10-Jahres-Investition für "
    if source.startswith(prefix):
        return source[len(prefix):]
    if source.startswith("Summe 10-Jahres Netzausbau"):
        return "Summe Netzausbau"
    if "erzeugungsgetrieben" in source:
        return "davon überwiegend erzeugungsgetrieben"
    if "verbrauchsbedingt" in source:
        return "davon überwiegend verbrauchsbedingt"
    return source


def _amount(source: str) -> str:
    digits = source.replace(".", "").replace("€", "").replace(" ", "")
    return str(int(digits))


def _summary(words: list[tuple]) -> ExtractedTable:
    columns_a = [1154.67, 1141.95, 1107.75, 1055.67, 907.59, 858.99, 819.99, 771.87, 725.55]
    columns_b = [1154.67, 1141.95, 1107.75, 1055.67, 907.59]
    source_rows = _grid(words, (265.92, 280.44), [280.32, 287.64, 294.84, 302.04], columns_a)
    source_rows += _grid(words, (304.32, 311.64), [311.52, 318.84, 326.04, 333.24], columns_b)
    values = {(level, _category(category)): _amount(amount) for level, entries in source_rows for category, amount in entries.items()}
    rows = [[level, category, values[(level, category)]] for level in LEVELS for category in CATEGORIES]
    provenance = [RowProvenance(5, (265.92, 725.55, 333.24, 1154.67), "summary-grids") for _ in rows]
    return ExtractedTable("aggregierte-10-jahresplanung", "Teil 1: Aggregierte 10-Jahresplanung der unteren Netzebenen", ["Netzebene", "Investitionsart", "Betrag_EUR"], rows, [5], provenance)


def _detail(words: list[tuple]) -> ExtractedTable:
    rows = []
    provenance = []
    for x0, x1 in zip(DETAIL_ROWS, DETAIL_ROWS[1:]):
        rows.append([_cell(words, x0, x1, lo, hi) for hi, lo in zip(DETAIL_COLUMNS, DETAIL_COLUMNS[1:])])
        provenance.append(RowProvenance(5, (x0, DETAIL_COLUMNS[-1], x1, DETAIL_COLUMNS[0]), "detail-grid"))
    return ExtractedTable("massnahmenplan", "Teil 2: Maßnahmenplan aller Spannungsebenen", DETAIL_HEADERS, rows, [5], provenance)


def extract_tables(request: ExtractionRequest) -> ExtractionResult:
    compatibility = can_handle(request.source)
    if not compatibility.supported:
        raise ValueError(compatibility.reason)
    with fitz.open(request.source) as document:
        if len(document) != 5:
            raise ValueError("expected five pages")
        words = document[4].get_text("words", sort=False)
    summary, detail = _summary(words), _detail(words)
    findings = []
    if len(words) < 3000:
        findings.append(QaFinding("text-layer", "error", "page 5 text layer is incomplete"))
    if len(summary.rows) != 24 or any(len(row) != 3 for row in summary.rows):
        findings.append(QaFinding("summary-shape", "error", "expected 24 x 3 summary rows"))
    if len(detail.rows) != 52 or any(len(row) != 20 for row in detail.rows):
        findings.append(QaFinding("detail-shape", "error", "expected 52 x 20 detail rows"))
    if len({row[0] for row in detail.rows}) != len(detail.rows):
        findings.append(QaFinding("detail-key", "error", "detail row identifiers are not unique"))
    return ExtractionResult("bielefelder-netz-2022", "1.0.0", SOURCE_SHA256, [summary, detail], QaReport(findings))
