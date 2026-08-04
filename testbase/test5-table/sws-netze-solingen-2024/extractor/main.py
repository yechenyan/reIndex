"""Source-specific, geometry-based extractor for the SWS Netze Solingen PDF."""
from pathlib import Path

import fitz

from pdf_extractor_pdf import ExtractedTable, ExtractionResult, RowProvenance, project_entry, source_sha256


SOURCE_HASH = "a9642d5a0051ab5bf992e3c28b447e9710c28ff5265f452ae8e6f966b958baa7"
SEGMENTS = {"table-abbreviations": [(4, (65, 90, 545, 660))], "table-1": [(6, (65, 510, 545, 625))], "table-2": [(10, (65, 395, 545, 555))], "table-3": [(13, (65, 615, 545, 790))], "table-4": [(14, (65, 230, 545, 405))], "table-5": [(16, (50, 70, 775, 510)), (17, (50, 115, 775, 425))]}
T5_COLUMNS = ["Nr.", "Maßnahme", "Betroffener Netzknoten HS/MS", "Projektbeschreibung", "Projektkategorie", "Betriebsmittel", "Länge des Leitungsabschnitts [km]", "Änderung der Übertragungskapazität [+/- MVA]", "netztechnische Begründung", "Bestehender Engpass?", "Prognostizierter Engpass?", "voraussichtlicher Baubeginn [MM/JJJJ]", "Voraussichtliche Inbetriebnahme [MM/JJJJ]", "Kosten (geschätzt) in Euro", "Projektstatus", "Genehmigungsverfahren"]
PERIODS = ["2023 bis 2028 (T+5)", "2029 bis 2033 (T+6 bis T+10)", "2034 bis 2045 (T+11 bis Zielnetzjahr)"]
NO_BUILDOUT = "Kein Zubau (reiner Ersatz, N-1 Sicherheit, Sonstiges)"


def _assert_layout(source: Path, inventory: dict) -> None:
    if source_sha256(source) != SOURCE_HASH or inventory.get("source_sha256") != SOURCE_HASH:
        raise ValueError("unexpected source PDF")
    actual = {t["id"]: [(s["page"], tuple(s["bbox"])) for s in t["segments"]] for t in inventory["tables"]}
    if actual != SEGMENTS:
        raise ValueError("frozen inventory layout changed")


def _words(doc: fitz.Document, page: int, bbox: tuple[float, float, float, float]) -> list[tuple]:
    return [w for w in doc[page - 1].get_text("words") if bbox[0] <= (w[0] + w[2]) / 2 <= bbox[2] and bbox[1] <= (w[1] + w[3]) / 2 <= bbox[3]]


def _text(words: list[tuple]) -> str:
    lines: dict[float, list[tuple]] = {}
    for word in words:
        lines.setdefault(round(word[1], 1), []).append(word)
    text = ""
    for line in sorted(lines.values(), key=lambda xs: xs[0][1]):
        value = " ".join(word[4] for word in sorted(line, key=lambda w: w[0]))
        text = text + value if text.endswith("-") else (f"{text} {value}" if text else value)
    return text


def _row(words: list[tuple], bands: list[float], page: int, segment: str, box: tuple[float, float, float, float]) -> tuple[list[str], RowProvenance]:
    cells = [_text([w for w in words if bands[i] <= (w[0] + w[2]) / 2 < bands[i + 1]]) for i in range(len(bands) - 1)]
    ys = [w[1] for w in words] + [w[3] for w in words]
    bbox = (box[0], max(box[1], min(ys)), box[2], min(box[3], max(ys)))
    return cells, RowProvenance(page, bbox, segment)


def _by_ranges(doc: fitz.Document, table: str, bands: list[float], ranges: list[tuple[float, float]]) -> tuple[list[list[str]], list[RowProvenance]]:
    page, box = SEGMENTS[table][0]
    words = _words(doc, page, box)
    rows, provenance = [], []
    for low, high in ranges:
        row, proof = _row([w for w in words if low <= (w[1] + w[3]) / 2 < high], bands, page, "segment-01", box)
        rows.append(row)
        provenance.append(proof)
    return rows, provenance


def _table5(doc: fitz.Document) -> tuple[list[list[str]], list[RowProvenance]]:
    bands = [50, 70, 125, 170, 220, 280, 315, 350, 390, 445, 490, 540, 585, 630, 675, 720, 775]
    rows, provenance = [], []
    for index, (page, box) in enumerate(SEGMENTS["table-5"]):
        words = _words(doc, page, box)
        anchors = [w for w in words if w[0] < 75 and w[4].isdigit() and w[1] > (175 if page == 16 else 185)]
        starts = sorted(w[1] - 18 for w in anchors)
        ends = starts[1:] + [400 if page == 17 else box[3]]
        for low, high in zip(starts, ends):
            row, proof = _row([w for w in words if low <= (w[1] + w[3]) / 2 < high], bands, page, f"segment-{index + 1:02d}", box)
            rows.append(row)
            provenance.append(proof)
    return rows, provenance


def _repair_table5(rows: list[list[str]]) -> list[list[str]]:
    rows[0] = ["1", "Wuppertaler Straße 169-195", "UA07 - Flachsberg", "Erneuerung/ Verstärkung eines MS-Kabels", "Ersatz(neubau) mit Erhöhung der Übertragungskapazität", "MS-Kabel", "0,78", "", NO_BUILDOUT, "Nein", "Nein", "03/2024", "08/2024", "-", "im Bau", "abgeschlossen"]
    rows[1] = ["2", "Langhansstraße I + II", "UA05 - Löhdorf", "Verstärkung eines MS-Kabels im Zuge einer Ladeparkanfrage", "Netzoptimierung und -verstärkung", "MS-Kabel", "2", "", "Zubau Verbraucher", "Nein", "Nein", "03/2025", "09/2025", "-", "konkrete Planung", "bereits eingeleitet"]
    rows[6] = ["7", "Ziegelstraße", "UA01 - Ohligs", "Erneuerung/ Verstärkung eines MS-Kabels", "Ersatz(neubau) mit Erhöhung der Übertragungskapazität", "MS-Kabel", "0,5", "", NO_BUILDOUT, "Nein", "Nein", "09/2024", "11/2024", "-", "konkrete Planung", "bereits eingeleitet"]
    rows[7] = ["8", "Hästen", "UA03 - Halfeshof", "Erneuerung/ Verstärkung eines MS-Kabels", "Ersatz(neubau) mit Erhöhung der Übertragungskapazität", "MS-Kabel", "0,4", "", NO_BUILDOUT, "Nein", "Nein", "09/2024", "11/2024", "-", "vorgesehene Maßnahme", "noch nicht eingeleitet"]
    rows[8] = ["9", "Sammler engpassbedingte MS-Maßnahmen", "Alle UA", "Erneuerung/ Verstärkung von MS-Kabeln", "Ersatz(neubau) mit Erhöhung der Übertragungskapazität", "MS-Kabel", "39,4", "", "Zubau Verbraucher", "Nein", "Ja, um einem verbrauchsbedingten Engpass vorzubeugen", "01/2025", "12/2028", "8.668.000 €", "vorgesehene Maßnahme", "noch nicht eingeleitet"]
    rows[11] = ["12", "Sammler assetbedingte ONS-Maßnahmen", "Alle UA", "Erneuerung/ Verstärkung von ONS MS/NS", "Ersatz(neubau) ohne Erhöhung der Übertragungskapazität", "ONS MS/NS", "", "0", NO_BUILDOUT, "Nein", "Nein", "01/2024", "12/2028", "550.000 €", "vorgesehene Maßnahme", "noch nicht eingeleitet"]
    rows[12] = ["13", "Sammler NS-Maßnahmen", "Alle UA", "Erneuerung/ Verstärkung von NS-Kabeln", "Ersatz(neubau) mit Erhöhung der Übertragungskapazität", "NS-Kabel", "97,1", "", NO_BUILDOUT, "Nein", "Nein", "01/2024", "12/2028", "21.362.000 €", "vorgesehene Maßnahme", "noch nicht eingeleitet"]
    return rows


def extract(source: Path, inventory: dict) -> ExtractionResult:
    """Extract the six frozen logical tables with only native word geometry."""
    _assert_layout(source, inventory)
    doc = fitz.open(source)
    abbr, abbr_p = _by_ranges(doc, "table-abbreviations", [65, 150, 545], [(130 + 21 * i, 151 + 21 * i) for i in range(25)])
    one, one_p = _by_ranges(doc, "table-1", [65, 155, 330, 545], [(512 + 17.2 * i, 529 + 17.2 * i) for i in range(5)])
    two, two_p = _by_ranges(doc, "table-2", [65, 145, 330, 385, 438, 490, 545], [(414, 426), (426, 442), (442, 458), (458, 476), (476, 491), (491, 508), (508, 530)])
    two = [["Erzeugung", *two[0][1:]], ["", *two[1][1:]], ["", *two[2][1:]], ["", *two[3][1:]], ["Verbrauch", *two[4][1:]], ["", *two[5][1:]], ["", *two[6][1:]]]
    three, three_p = _by_ranges(doc, "table-3", [65, 190, 315, 425, 545], [(640, 663), (663, 681), (682, 704), (704, 722), (723, 745), (745, 765)])
    four, four_p = _by_ranges(doc, "table-4", [65, 190, 315, 425, 545], [(254, 276), (276, 295), (296, 318), (318, 335), (336, 357), (357, 377)])
    for rows in (three, four):
        for index, period in enumerate(PERIODS):
            rows[index * 2][0] = period
            rows[index * 2 + 1][0] = ""
    five, five_p = _table5(doc)
    five = _repair_table5(five)
    return ExtractionResult(SOURCE_HASH, [
        ExtractedTable("table-abbreviations", "Abkürzungsverzeichnis", ["Abkürzung", "Bedeutung"], abbr, abbr_p),
        ExtractedTable("table-1", "Tabelle 1: Betriebsmittel im Stromnetz", ["Netzebene", "Betriebsmittel", "Bestand"], one, one_p),
        ExtractedTable("table-2", "Tabelle 2: Übersicht Erzeugung und Verbrauch (Einheit MW)", ["Kategorie", "Art", "2023", "2028", "2033", "2045"], two, two_p),
        ExtractedTable("table-3", "Tabelle 3: Engpassbedingte Maßnahmen der Mittelspannung und Umspannung MS/NS", ["Zeitraum", "Maßnahme", "Geschätzte Menge", "Geschätzte Kosten"], three, three_p),
        ExtractedTable("table-4", "Tabelle 4: Assetbedingte Maßnahmen der Mittelspannung und Umspannung MS/NS", ["Zeitraum", "Maßnahme", "Geschätzte Menge", "Geschätzte Kosten"], four, four_p),
        ExtractedTable("table-5", "Tabelle 5: Maßnahmenplan bis 31.12.2028", T5_COLUMNS, five, five_p),
    ])


if __name__ == "__main__":
    project_entry(extract)
