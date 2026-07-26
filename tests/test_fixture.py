import csv
import hashlib
from collections import Counter
from pathlib import Path

import pymupdf
import yaml


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "testbase" / "test1"
SOURCE_NAME = "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
SOURCE = FIXTURE / "raw" / SOURCE_NAME
PACKAGE = FIXTURE / "reIndex"
DOCUMENT = PACKAGE / "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022"
EXPECTED_SHA256 = "3dc36a9917ac29b387c8fcc6e1a856f26e4fc0660d4e847a5070ee7dca0af497"


def metadata(path: Path) -> dict:
    _, frontmatter, _ = path.read_text(encoding="utf-8").split("---", 2)
    return yaml.safe_load(frontmatter)


def read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        return next(reader), list(reader)


def test_source_pdf_is_unchanged() -> None:
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED_SHA256
    assert pymupdf.open(SOURCE).page_count == 5
    assert not (FIXTURE / "raw" / "nap_2024_angepasste_fassung_vom_07_08_2024.pdf").exists()


def test_node_tree_and_resources_are_valid() -> None:
    nodes = sorted(PACKAGE.rglob("*.node.md"))
    assert len(nodes) == 8
    records = [metadata(node) for node in nodes]
    assert len({record["id"] for record in records}) == 8
    assert Counter(record["kind"] for record in records) == {
        "group": 2,
        "text": 3,
        "image": 1,
        "table": 2,
    }
    for node, record in zip(nodes, records, strict=True):
        assert record["spec"] == "reindex/node@0.1"
        if source := record.get("source"):
            assert source["uri"] == f"raw://{SOURCE_NAME}"
            assert source["sha256"] == EXPECTED_SHA256
            if locator := source.get("locator"):
                assert 1 <= locator["pages"][0] <= locator["pages"][1] <= 5
        if resource := record.get("resource"):
            path = node.parent / resource["uri"].removeprefix("./")
            assert path.is_file()
            assert hashlib.sha256(path.read_bytes()).hexdigest() == resource["sha256"]


def test_aggregate_table_is_complete() -> None:
    headers, rows = read_csv(DOCUMENT / "0005.csv")
    assert headers == ["Netzebene", "Investitionsart", "Betrag_EUR"]
    assert len(rows) == 24
    assert rows[:3] == [
        ["Mittelspannung", "Neubau", "3242160"],
        ["Mittelspannung", "Ersatz(neubau) mit Erhöhung der Übertragungskapazität", "19452960"],
        ["Mittelspannung", "Netzoptimierung und -verstärkung", "8105400"],
    ]
    record = metadata(DOCUMENT / "0005.node.md")
    assert record["table"]["row_count"] == 24
    assert [column["name"] for column in record["table"]["columns"]] == headers


def test_measure_table_preserves_all_cells() -> None:
    headers, rows = read_csv(DOCUMENT / "0006.csv")
    assert len(headers) == 20
    assert len(rows) == 52
    assert len({row[0] for row in rows}) == 52
    by_id = {row[0]: row for row in rows}
    assert by_id["4aa"][1:8] == [
        "UW Universität - UW Zwinger",
        "keine Betroffenheit",
        "Kabelneubau / Netzverstärkung zur Optimierung des 110kV-Kabelnetzes",
        "Neubau",
        "110-kV-Kabel",
        "3,3",
        "+152",
    ]
    assert by_id["14a"][15:18] == ["5.731.000 €", "im Bau", "bereits eingeleitet"]
    assert by_id["91"][1] == "UW Kraftwerk 10kV-Schaltanlage"
    record = metadata(DOCUMENT / "0006.node.md")
    assert record["table"]["row_count"] == 52
    assert [column["name"] for column in record["table"]["columns"]] == headers
    assert record["table"]["primary_key"] == ["lfd. Nr."]


def test_visual_resources_are_high_resolution() -> None:
    expected_minimums = {
        "0002.jpg": (1400, 1200),
        "0005.png": (2000, 350),
        "0006.png": (4400, 850),
    }
    for name, minimum in expected_minimums.items():
        pixmap = pymupdf.Pixmap(str(DOCUMENT / name))
        assert pixmap.width >= minimum[0]
        assert pixmap.height >= minimum[1]


def test_table_visuals_belong_to_table_nodes() -> None:
    for number in ("0005", "0006"):
        node = DOCUMENT / f"{number}.node.md"
        assert metadata(node)["kind"] == "table"
        body = node.read_text(encoding="utf-8")
        assert f"[Open {number}.png](./{number}.png)" in body
        assert not (DOCUMENT / f"{number}.png.node.md").exists()
    assert not (DOCUMENT / "0008.node.md").exists()
