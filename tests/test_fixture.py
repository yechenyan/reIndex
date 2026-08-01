import csv
import hashlib
from collections import Counter
from pathlib import Path

import yaml
from PIL import Image
from pypdfium2 import PdfDocument

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "testbase" / "test1"
SOURCE_NAME = "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
SOURCE = FIXTURE / "test1" / SOURCE_NAME
PACKAGE = FIXTURE / "reIndex" / "test1"
DOCUMENT = PACKAGE / "bielefelder-netz-gmbh-netzausbauplan-2022"
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
    assert len(PdfDocument(SOURCE)) == 5


def test_node_tree_and_resources_are_valid() -> None:
    nodes = sorted(PACKAGE.rglob("*.node.md"))
    records = [metadata(node) for node in nodes]
    assert len(nodes) == len({record["id"] for record in records}) == 8
    assert Counter(record["kind"] for record in records) == {
        "group": 2,
        "text": 3,
        "image": 1,
        "table": 2,
    }
    for node, record in zip(nodes, records, strict=True):
        assert record["spec"] == "reindex/node@1.0"
        if source := record.get("source"):
            assert source["uri"] == f"raw://{SOURCE_NAME}"
            assert source["sha256"] == EXPECTED_SHA256
        for value in [record.get("content"), *record.get("assets", [])]:
            if not value or value["uri"].startswith("raw://"):
                continue
            path = node.parent / value["uri"].removeprefix("./")
            assert hashlib.sha256(path.read_bytes()).hexdigest() == value["sha256"]


def test_tables_are_complete() -> None:
    aggregate = DOCUMENT / "00005--aggregierte-10-jahresplanung-untere-netzebenen.csv"
    headers, rows = read_csv(aggregate)
    assert headers == ["Netzebene", "Investitionsart", "Betrag_EUR"]
    assert len(rows) == 24
    record = metadata(aggregate.with_suffix(".node.md"))
    assert record["table"]["row_count"] == 24
    measures = DOCUMENT / "00006--massnahmenplan-aller-spannungsebenen.csv"
    headers, rows = read_csv(measures)
    assert len(headers) == 20
    assert len(rows) == 52
    assert len({row[0] for row in rows}) == 52
    assert metadata(measures.with_suffix(".node.md"))["table"]["primary_key"] == [
        "lfd. Nr."
    ]


def test_visual_resources_are_high_resolution() -> None:
    expected = {
        "00002--110kv-netzkarte-bielefeld.jpg": (1400, 1200),
        "00005--aggregierte-10-jahresplanung-untere-netzebenen.assets001.png": (
            2000,
            350,
        ),
        "00006--massnahmenplan-aller-spannungsebenen.assets001.png": (4400, 850),
    }
    for name, minimum in expected.items():
        with Image.open(DOCUMENT / name) as image:
            assert all(
                actual >= expected
                for actual, expected in zip(image.size, minimum, strict=True)
            )
