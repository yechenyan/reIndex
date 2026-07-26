from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pymupdf

from fixture_extract import (
    AGGREGATE_COLUMNS,
    MEASURE_COLUMNS,
    extract_aggregate_rows,
    extract_measure_rows,
    extract_text_sections,
    render_clip,
)
from fixture_nodes import (
    write_csv,
    write_group_node,
    write_image_node,
    write_table_node,
    write_text_node,
)

ROOT = Path(__file__).resolve().parent
SOURCE_NAME = "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
SOURCE = ROOT / "raw" / SOURCE_NAME
OUTPUT = ROOT / "reIndex"
DOCUMENT_DIR = OUTPUT / "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022"
EXPECTED_SHA256 = "3dc36a9917ac29b387c8fcc6e1a856f26e4fc0660d4e847a5070ee7dca0af497"

IDS = {
    "root": "056e95b3-aad8-4740-af7e-973356ec4e44",
    "document": "be043b2f-0d57-40f7-aaa4-c7d6a99b55e6",
    "intro": "e2921488-8b2e-480c-9c34-7d3fe639787c",
    "map": "c8f85823-e42b-4cb6-ae19-8aeaac00c08d",
    "planning": "f1592bf6-c0bc-4bba-9296-ae9aead4c660",
    "measures_text": "a0f37f35-0c18-427a-b61a-6d7d4fb5a47b",
    "aggregate": "333563cf-1334-45a5-9d19-55f53f79757f",
    "measures": "0d08c3e5-fc02-4614-9666-ca73f35b9211",
}


def verify_source() -> None:
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError(f"Unexpected source SHA-256: {digest}")


def build_images(document: pymupdf.Document) -> None:
    map_data = document.extract_image(3)
    map_path = DOCUMENT_DIR / "0002.jpg"
    map_path.write_bytes(map_data["image"])
    write_image_node(
        DOCUMENT_DIR / "0002.node.md",
        IDS["map"],
        "110kV-Netzkarte Bielefeld",
        "Konzessionsgebiet, bestehendes 110kV-Netz und geplante Änderungen.",
        SOURCE_NAME,
        EXPECTED_SHA256,
        (2, 2),
        map_path,
        "image/jpeg",
        (
            "Die Karte zeigt Bielefeld und Werther als blaues Konzessionsgebiet, "
            "Steinhagen westlich davon, bestehende Leitungsverläufe in dunkelgrau "
            "oder schwarz, geplante Änderungen in grün und Umspannpunkte als rote Kreise."
        ),
        "Werther\nBielefeld\nSteinhagen",
    )

    page = document[4]
    aggregate_image = DOCUMENT_DIR / "0005.png"
    render_clip(page, aggregate_image, (30, 264, 470, 340), scale=5)

    measures_image = DOCUMENT_DIR / "0006.png"
    render_clip(page, measures_image, (36, 456, 1155, 677), scale=4)


def build_tables(document: pymupdf.Document) -> None:
    page = document[4]
    aggregate_rows = extract_aggregate_rows(page)
    aggregate_csv = DOCUMENT_DIR / "0005.csv"
    write_csv(aggregate_csv, [column["name"] for column in AGGREGATE_COLUMNS], aggregate_rows)
    write_table_node(
        DOCUMENT_DIR / "0005.node.md",
        IDS["aggregate"],
        "Aggregierte 10-Jahresplanung der unteren Netzebenen",
        "Investitionen nach Netzebene und Investitionsart in Euro.",
        SOURCE_NAME,
        EXPECTED_SHA256,
        (5, 5),
        aggregate_csv,
        AGGREGATE_COLUMNS,
        aggregate_rows,
        "Eine Zeile entspricht einer Netzebene und einer Investitionsart.",
        preview_indices=[0, 1, 2],
        warnings=[
            "CSV ist deterministisch in ein langes, maschinenlesbares Format normalisiert.",
            "0005.png ist die visuelle Referenz derselben Tabelle und kein eigener Bild-Node.",
        ],
        visual_path=DOCUMENT_DIR / "0005.png",
    )

    measure_rows = extract_measure_rows(page)
    measures_csv = DOCUMENT_DIR / "0006.csv"
    write_csv(measures_csv, [column["name"] for column in MEASURE_COLUMNS], measure_rows)
    write_table_node(
        DOCUMENT_DIR / "0006.node.md",
        IDS["measures"],
        "Maßnahmenplan aller Spannungsebenen für zehn Jahre",
        "52 geplante Netzmaßnahmen mit Projekt-, Termin-, Kosten- und Statusangaben.",
        SOURCE_NAME,
        EXPECTED_SHA256,
        (5, 5),
        measures_csv,
        MEASURE_COLUMNS,
        measure_rows,
        "Eine Zeile entspricht einer Maßnahme mit eindeutiger laufender Nummer.",
        preview_indices=[0, 1, 4, 12, 13, 15, 16, 19],
        warnings=[
            "Zeilenumbrüche innerhalb der PDF-Zellen wurden zu einfachen Leerzeichen normalisiert.",
            "0006.png ist die visuelle Referenz derselben Tabelle und kein eigener Bild-Node.",
        ],
        primary_key=["lfd. Nr."],
        visual_path=DOCUMENT_DIR / "0006.png",
    )


def main() -> None:
    verify_source()
    document = pymupdf.open(SOURCE)
    if document.page_count != 5:
        raise ValueError(f"Expected 5 pages, found {document.page_count}")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    DOCUMENT_DIR.mkdir(parents=True)

    write_group_node(
        OUTPUT / "index.node.md",
        IDS["root"],
        "Bielefelder Netz GmbH Netzausbauplan 2022",
        "Testkollektion mit Original-PDF, strukturiertem Text, Tabellen und visuellen Referenzen.",
    )
    write_group_node(
        DOCUMENT_DIR / "index.node.md",
        IDS["document"],
        "Netzausbauplan nach §14d EnWG",
        "Netzausbauplan 2022 der Bielefelder Netz GmbH einschließlich Anhang.",
        SOURCE_NAME,
        EXPECTED_SHA256,
    )

    intro, planning, measures_text = extract_text_sections(document)
    write_text_node(DOCUMENT_DIR / "0001.node.md", IDS["intro"], "Titel, Inhalt und Einleitung", "Dokumentübersicht und Beschreibung des Netzgebiets.", SOURCE_NAME, EXPECTED_SHA256, (1, 1), intro)
    write_text_node(DOCUMENT_DIR / "0003.node.md", IDS["planning"], "C. Planungsgrundlagen", "Lastentwicklung, Elektromobilität, Wärmeversorgung und dezentrale Erzeugung.", SOURCE_NAME, EXPECTED_SHA256, (2, 3), planning)
    write_text_node(DOCUMENT_DIR / "0004.node.md", IDS["measures_text"], "D bis F: Ausbau, Dienstleistungen und Sonstiges", "Einordnung der Ausbauplanung sowie Aussagen zu Flexibilität und sonstigen Themen.", SOURCE_NAME, EXPECTED_SHA256, (3, 4), measures_text)
    build_images(document)
    build_tables(document)
    document.close()
    print("Generated 8 Nodes, 2 CSV tables, and 3 visual resources from 5 PDF pages")


if __name__ == "__main__":
    main()
