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
    source_sha256,
)

SOURCE_SHA256 = "a9642d5a0051ab5bf992e3c28b447e9710c28ff5265f452ae8e6f966b958baa7"
TABLE5_X = [58.4, 73.8, 126.5, 168.4, 223.6, 279.2, 312.0, 351.0, 390.0,
            446.7, 496.3, 546.0, 588.4, 630.9, 679.1, 725.9, 764.9]


def can_handle(source: Path) -> CompatibilityReport:
    digest = source_sha256(Path(source))
    return CompatibilityReport(
        supported=digest == SOURCE_SHA256,
        reason="exact source hash match" if digest == SOURCE_SHA256 else "unknown source hash",
        source_sha256=digest,
    )


def _join_lines(lines: list[str]) -> str:
    value = ""
    for line in lines:
        if not value:
            value = line
        elif value.endswith("/"):
            value += line
        elif value.endswith(" -"):
            value += " " + line
        elif value.endswith("-"):
            token = value.rsplit(" ", 1)[-1][:-1]
            value = value + line if token.isupper() else value[:-1] + line
        else:
            value += " " + line
    return value.replace(" | + ||", " I + II")


def _cell(words: list[tuple], rect: tuple[float, float, float, float]) -> str:
    selected = [
        word for word in words
        if rect[0] < (word[0] + word[2]) / 2 < rect[2]
        and rect[1] < (word[1] + word[3]) / 2 < rect[3]
    ]
    grouped: dict[tuple[int, int], list[tuple]] = {}
    for word in selected:
        grouped.setdefault((word[5], word[6]), []).append(word)
    lines = [" ".join(str(word[4]) for word in sorted(line, key=lambda item: item[0]))
             for line in grouped.values()]
    return _join_lines(lines)


def _grid(page: fitz.Page, xs: list[float], ys: list[float], segment: str, words=None):
    words = page.get_text("words", sort=True) if words is None else words
    rows, provenance = [], []
    for y0, y1 in zip(ys, ys[1:]):
        rows.append([_cell(words, (x0, y0, x1, y1)) for x0, x1 in zip(xs, xs[1:])])
        provenance.append(RowProvenance(page=page.number + 1, bbox=(xs[0], y0, xs[-1], y1), segment=segment))
    return rows, provenance


def _table(table_id: str, title: str, headers: list[str], rows, pages, provenance):
    return ExtractedTable(table_id, title, headers, rows, pages, provenance)


def _simple_tables(document: fitz.Document) -> list[ExtractedTable]:
    page = document[3]
    ys = [129.84 + index * (656.24 - 129.84) / 25 for index in range(26)]
    rows, prov = _grid(page, [71.15, 163.1, 535.57], ys, "page-4")
    tables = [_table("abkuerzungsverzeichnis", "Abkürzungsverzeichnis",
                     ["", ""], rows, [4], prov)]

    rows, prov = _grid(document[5], [71.4, 170.3, 340.2, 535.32],
                       [516.36, 533.9, 551.0, 568.2, 585.5, 602.88], "page-6")
    tables.append(_table("tabelle-1-betriebsmittel-stromnetz",
                         "Tabelle 1: Betriebsmittel im Stromnetz",
                         ["", "", ""], rows, [6], prov))

    page = document[9]
    words = page.get_text("words", sort=True)
    ys = [416.9, 433.2, 449.4, 465.6, 481.9, 498.4, 514.4, 530.95]
    rows, prov = _grid(page, [70.92, 156.0, 325.7, 378.0, 430.3, 482.6, 535.14], ys, "page-10", words)
    for row in rows:
        row[0] = ""
    rows[0][0] = _cell(words, (70.92, 416.9, 156.0, 481.9))
    rows[4][0] = _cell(words, (70.92, 481.9, 156.0, 530.95))
    tables.append(_table("tabelle-2-erzeugung-verbrauch",
                         "Tabelle 2: Übersicht Erzeugung und Verbrauch (Einheit MW)",
                         ["", "", "2023", "2028", "2033", "2045"], rows, [10], prov))
    return tables


def _measures(document: fitz.Document, page_number: int, table_id: str, title: str,
              xs: list[float], ys: list[float]) -> ExtractedTable:
    page = document[page_number - 1]
    words = page.get_text("words", sort=True)
    rows, prov = _grid(page, xs, ys, f"page-{page_number}", words)
    for index in (0, 2, 4):
        rows[index][0] = _cell(words, (xs[0], ys[index], xs[1], ys[index + 2]))
        rows[index + 1][0] = ""
    return _table(table_id, title,
                  ["Zeitraum", "Maßnahme", "Geschätzte Menge", "Geschätzte Kosten"],
                  rows, [page_number], prov)


def _table5(document: fitz.Document) -> ExtractedTable:
    rows16, prov16 = _grid(document[15], TABLE5_X,
                           [176.94, 219.14, 260.98, 302.88, 344.76, 386.7, 428.64, 470.52, 512.4],
                           "page-16")
    rows17, prov17 = _grid(document[16], TABLE5_X,
                           [191.73, 233.86, 275.78, 317.62, 359.52, 401.48], "page-17")
    headers = ["Nr.", "Maßnahme", "Betroffener Netzknoten HS/MS", "Projektbeschreibung",
               "Projektkategorie", "Betriebsmittel", "Länge des Leitungsabschnitts [km]",
               "Änderung der Übertragungskapazität [+/- MVA]", "netztechnische Begründung",
               "Bestehender Engpass?", "Prognostizierter Engpass?",
               "voraussichtlicher Baubeginn [MM/JJJJ]",
               "Voraussichtliche Inbetriebnahme [MM/JJJJ]", "Kosten (geschätzt) in Euro",
               "Projektstatus", "Genehmigungsverfahren"]
    return _table("tabelle-5-massnahmenplan", "Tabelle 5: Maßnahmenplan bis 31.12.2028",
                  headers, rows16 + rows17, [16, 17], prov16 + prov17)


def extract_tables(request: ExtractionRequest) -> ExtractionResult:
    compatibility = can_handle(request.source)
    if not compatibility.supported:
        raise ValueError(compatibility.reason)
    with fitz.open(request.source) as document:
        tables = _simple_tables(document)
        tables.append(_measures(document, 13, "tabelle-3-engpassbedingte-massnahmen",
                                "Tabelle 3: Engpassbedingte Maßnahmen der Mittelspannung und Umspannung MS/NS",
                                [71.4, 198.5, 310.8, 423.0, 535.32],
                                [641.4, 661.9, 682.6, 703.2, 723.7, 744.4, 765.0]))
        tables.append(_measures(document, 14, "tabelle-4-assetbedingte-massnahmen",
                                "Tabelle 4: Assetbedingte Maßnahmen der Mittelspannung und Umspannung MS/NS",
                                [71.4, 198.5, 310.7, 422.9, 535.2],
                                [255.0, 275.5, 296.2, 316.8, 337.3, 358.0, 378.6]))
        tables.append(_table5(document))
        findings = []
        expected_shapes = [(25, 2), (5, 3), (7, 6), (6, 4), (6, 4), (13, 16)]
        if len(document) != 17 or [(len(t.rows), len(t.headers)) for t in tables] != expected_shapes:
            findings.append(QaFinding("layout-drift", "error", "Expected page count or table shapes changed"))
        anchor_checks = [
            (tables[0].rows[0][0] == "BDEW" and tables[0].rows[-1][0] == "VVNB"
             and all(row[0] for row in tables[0].rows), "abbreviation anchors"),
            (tables[1].rows[0][0] == "Netzebene 4" and tables[1].rows[-1][0] == "Netzebene 7"
             and all(row[0] for row in tables[1].rows), "network asset anchors"),
            (tables[2].rows[0][1] == "Photovoltaik" and tables[2].rows[-1][1] == "Verkehr"
             and all(row[1] for row in tables[2].rows), "generation/consumption anchors"),
            (all(row[1] for row in tables[3].rows) and tables[3].rows[-1][1] == "Anlagenstandorte",
             "congestion measure anchors"),
            (all(row[1] for row in tables[4].rows) and tables[4].rows[-1][1] == "Anlagenstandorte",
             "asset measure anchors"),
            (all(row[0] and row[1] and row[3] for row in tables[5].rows), "measure plan key columns"),
        ]
        for ok, message in anchor_checks:
            if not ok:
                findings.append(QaFinding("source-anchor", "error", f"Missing {message}"))
        if [row[0] for row in tables[-1].rows] != [str(index) for index in range(1, 14)]:
            findings.append(QaFinding("row-identifiers", "error", "Table 5 row identifiers are not 1 through 13"))
    return ExtractionResult("sws-netze-solingen-2024", "2.0.0", SOURCE_SHA256,
                            tables, QaReport(findings))
