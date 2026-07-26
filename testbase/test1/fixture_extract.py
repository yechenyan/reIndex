from __future__ import annotations

import re
from pathlib import Path

import pymupdf

AGGREGATE_COLUMNS = [
    {"name": "Netzebene", "type": "string", "description": "Betroffene untere Netzebene."},
    {"name": "Investitionsart", "type": "string", "description": "Kategorie der Zehnjahresinvestition."},
    {"name": "Betrag_EUR", "type": "integer", "description": "Im PDF ausgewiesener Betrag.", "unit": "EUR"},
]

MEASURE_NAMES = [
    "lfd. Nr.",
    "Maßnahme",
    "Betroffener Netzknoten im überlagerten HöS-Netz",
    "Kurze Projektbeschreibung",
    "Projektkategorie",
    "Betriebsmittel",
    "Länge Leitungsabschnitt [km]",
    "Änderung Übertragungskapazität [+/- MVA]",
    "Netztechnische Begründung",
    "Überwiegender Ausbaugrund",
    "Bestehenden Engpass beheben",
    "Prognostiziertem Engpass vorbeugen",
    "Voraussichtlicher Baubeginn [MM/JJJJ]",
    "Voraussichtliche Inbetriebnahme [MM/JJJJ]",
    "Verzögerungsgrund",
    "Kosten (geschätzt) in Euro",
    "Projektstatus",
    "Stand Genehmigungsverfahren",
    "Geprüfte Alternativen",
    "Vorrangige Netz- oder Umspannebene",
]

MEASURE_DESCRIPTIONS = [
    "Vom Betreiber vergebene laufende Identifikation der Maßnahme.",
    "Bezeichnung der Maßnahme oder Anlage.",
    "Betroffenheit im vorgelagerten Höchstspannungsnetz.",
    "Kurzbeschreibung des geplanten Projekts.",
    "Neubau-, Ersatz-, Optimierungs- oder Rückbaukategorie.",
    "Betroffenes technisches Betriebsmittel.",
    "Länge des betroffenen Leitungsabschnitts laut PDF.",
    "Änderung der Übertragungskapazität laut PDF.",
    "Technische Begründung für die Maßnahme.",
    "Überwiegender erzeugungs- oder verbrauchsbezogener Grund.",
    "Angabe zur Behebung eines bestehenden Engpasses.",
    "Angabe zur Vorbeugung eines prognostizierten Engpasses.",
    "Geplanter Beginn im Originalformat.",
    "Geplante Inbetriebnahme im Originalformat.",
    "Angegebener Grund einer Verzögerung.",
    "Kostenschätzung einschließlich Originalformat und Währungssymbol.",
    "Projektstatus zum Dokumentstand.",
    "Stand des Genehmigungsverfahrens.",
    "Vom Betreiber angegebene geprüfte Alternative.",
    "Vorrangig betroffene Netz- oder Umspannebene.",
]

MEASURE_COLUMNS = [
    {"name": name, "type": "string", "description": description}
    for name, description in zip(MEASURE_NAMES, MEASURE_DESCRIPTIONS, strict=True)
]

COLUMN_BOUNDARIES = [
    36.267999, 48.988001, 83.188, 135.268005, 283.347992, 331.947998,
    370.947998, 419.067993, 465.379438, 598.588013, 651.979414,
    699.628006, 747.268005, 787.107971, 829.947998, 900.756557,
    946.468018, 993.987976, 1024.827942, 1108.947937, 1154.448018,
]

EXPECTED_MEASURE_IDS = (
    "4aa", "5a", "6aa", "7a", "8aa", "9aa", "11aa", "14a", "15", "16",
    "17", "18", "19", "20", "21", "22a", "23", "24", "25", "26", "27",
    "28", "29a", "30", "31", "32", "33", "34", "35", "36", "37", "38",
    "39", "40", "41", "42", "43", "44", "45", "46", "47", "48", "49",
    "80", "84", "85", "86", "87", "88", "89", "90", "91",
)


def _clean_paragraph(text: str) -> str:
    text = re.sub(r"-[ \t]*\n[ \t]*(?=\w)", "", text.strip())
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r" {2,}", " ", text).strip()
    return text.replace("Stecker-PVAnlagen", "Stecker-PV-Anlagen")


def _paragraphs(text: str) -> list[str]:
    return [_clean_paragraph(part) for part in re.split(r"\n\s*\n", text) if part.strip()]


def _blocks(page: pymupdf.Page) -> list[tuple[float, str]]:
    result = []
    for x0, y0, x1, y1, text, *_ in page.get_text("blocks", sort=True):
        if text.strip() and y0 < 750:
            result.append((y0, text.strip()))
    return result


def extract_text_sections(document: pymupdf.Document) -> tuple[str, str, str]:
    p1, p2, p3, p4 = (_blocks(document[index]) for index in range(4))
    toc = next(text for y, text in p1 if 220 < y < 330 and text.startswith("A."))
    intro_parts = [text for y, text in p1 if 470 < y < 650]
    intro = [
        "# Netzausbauplan nach §14d EnWG",
        "",
        "<!-- reindex:page=1 -->",
        "## Inhalt",
        *[f"- {line.strip()}" for line in toc.splitlines()],
        "- ANHANG",
        "",
        "## A. Einleitung",
        "",
        *sum(([paragraph, ""] for text in intro_parts for paragraph in _paragraphs(text)), []),
    ]

    c_page2 = next(text for y, text in p2 if 570 < y < 750)
    c_page3 = next(text for y, text in p3 if y < 200)
    planning = ["# C. Planungsgrundlagen", "", "<!-- reindex:page=2 -->", ""]
    planning.extend(sum(([paragraph, ""] for paragraph in _paragraphs(c_page2)), []))
    planning.extend(["<!-- reindex:page=3 -->", ""])
    planning.extend(sum(([paragraph, ""] for paragraph in _paragraphs(c_page3)), []))

    d_page3 = [text for y, text in p3 if 670 < y < 750]
    d_to_f = ["# D bis F: Ausbau, Dienstleistungen und Sonstiges", "", "<!-- reindex:page=3 -->", ""]
    for text in d_page3:
        if text.startswith("D. "):
            d_to_f.extend(["## " + _clean_paragraph(text), ""])
        else:
            d_to_f.extend(sum(([paragraph, ""] for paragraph in _paragraphs(text)), []))
    d_to_f.extend(["<!-- reindex:page=4 -->", ""])
    for y, text in p4:
        clean = _clean_paragraph(text)
        if clean.startswith(("E. ", "F. ")) or clean == "ANHANG":
            d_to_f.extend(["## " + clean, ""])
        else:
            d_to_f.extend(sum(([paragraph, ""] for paragraph in _paragraphs(text)), []))
    return "\n".join(intro).strip(), "\n".join(planning).strip(), "\n".join(d_to_f).strip()


def _currency_value(value: str) -> str:
    digits = re.sub(r"[^\d]", "", value)
    if not digits:
        raise ValueError(f"Invalid currency cell: {value!r}")
    return digits


def extract_aggregate_rows(page: pymupdf.Page) -> list[list[str]]:
    table = page.find_tables().tables[1].extract()
    categories = [
        "Neubau",
        "Ersatz(neubau) mit Erhöhung der Übertragungskapazität",
        "Netzoptimierung und -verstärkung",
        "Summe Netzausbau",
        "davon überwiegend erzeugungsgetrieben",
        "davon überwiegend verbrauchsbedingt",
        "Ersatz(neubau) ohne Erhöhung der Übertragungskapazität",
        "Rückbau / Altlastentsorgung",
    ]
    rows = []
    for primary, secondary in zip(table[1:4], table[5:8], strict=True):
        level = _clean_paragraph(primary[1] or "")
        values = [_currency_value(value or "") for value in primary[2:8]]
        values.extend(_currency_value(value or "") for value in secondary[2:4])
        if sum(map(int, values[:3])) != int(values[3]):
            raise ValueError(f"Aggregate total mismatch for {level}")
        if int(values[4]) + int(values[5]) != int(values[3]):
            raise ValueError(f"Aggregate driver split mismatch for {level}")
        rows.extend([[level, category, value] for category, value in zip(categories, values, strict=True)])
    if len(rows) != 24:
        raise ValueError(f"Expected 24 aggregate rows, found {len(rows)}")
    return rows


def extract_measure_rows(page: pymupdf.Page) -> list[list[str]]:
    starts = []
    for x0, y0, x1, y1, text, *_ in page.get_text("blocks"):
        first = (text.strip().splitlines() or [""])[0]
        if x0 >= 470 and re.fullmatch(r"\d+[a-z]*", first):
            starts.append((x0, first))
    starts.sort()
    ids = tuple(identifier for _, identifier in starts)
    if ids != EXPECTED_MEASURE_IDS:
        raise ValueError(f"Unexpected measure IDs: {ids}")

    row_bounds = [x for x, _ in starts] + [676.428]
    words = []
    for x0, y0, x1, y1, text, *_ in page.get_text("words"):
        visual_x = 1191 - (y0 + y1) / 2
        visual_y = (x0 + x1) / 2
        if row_bounds[0] <= visual_y < row_bounds[-1]:
            words.append((visual_x, visual_y, text))

    rows = []
    for row_index, (top, identifier) in enumerate(starts):
        bottom = row_bounds[row_index + 1]
        cells = []
        for left, right in zip(COLUMN_BOUNDARIES, COLUMN_BOUNDARIES[1:]):
            selected = [word for word in words if top <= word[1] < bottom and left <= word[0] < right]
            selected.sort(key=lambda word: (round(word[1], 1), word[0]))
            cells.append(" ".join(word[2] for word in selected))
        if cells[0] != identifier or len(cells) != 20:
            raise ValueError(f"Invalid extracted measure row: {identifier}")
        rows.append(cells)
    return rows


def render_clip(page: pymupdf.Page, path: Path, clip: tuple[int, int, int, int], scale: int) -> None:
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=pymupdf.Rect(clip), alpha=False)
    pixmap.save(path)
