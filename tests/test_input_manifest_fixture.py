import csv
from pathlib import Path, PurePosixPath

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "testbase" / "test2"
MANIFEST = FIXTURE / "reIndex.md"
PDF_NAME = "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
AGGREGATE = "00005--aggregierte-10-jahresplanung-untere-netzebenen.csv"
MEASURES = "00006--massnahmenplan-aller-spannungsebenen.csv"


def manifest() -> dict:
    _, frontmatter, _ = MANIFEST.read_text(encoding="utf-8").split("---", 2)
    return yaml.safe_load(frontmatter)


def csv_shape(path: Path) -> tuple[list[str], int]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        return next(reader), sum(1 for _ in reader)


def test_input_manifest_references_safe_existing_items() -> None:
    value = manifest()
    assert value["spec"] == "reindex/input@1.0"
    assert "collection" not in value
    assert FIXTURE.name == "test2"
    items = value["items"]
    assert set(items) == {
        PDF_NAME,
        AGGREGATE,
        MEASURES,
        "costs_2020.csv",
        "README.md",
    }
    for relative in items:
        path = PurePosixPath(relative)
        assert not path.is_absolute() and ".." not in path.parts
        assert (FIXTURE / relative).is_file()
    for item in items.values():
        target = item.get("part_of") or item.get("derived_from")
        if target:
            assert target in items
    assert items["README.md"] == {"ignore": True}


def test_supplied_tables_match_declared_quality() -> None:
    items = manifest()["items"]
    assert items[PDF_NAME]["parse"]["tables"] == "supplied"
    for name in (AGGREGATE, MEASURES):
        item = items[name]
        assert item["part_of"] == PDF_NAME
        assert item["pages"] == [5, 5]
        headers, row_count = csv_shape(FIXTURE / name)
        quality = item["quality"]
        assert row_count == quality["expected_rows"]
        if expected := quality.get("expected_columns"):
            assert headers == expected
        if primary := quality.get("primary_key"):
            indices = [headers.index(column) for column in primary]
            with (FIXTURE / name).open(encoding="utf-8", newline="") as stream:
                rows = list(csv.reader(stream))[1:]
            keys = [tuple(row[index] for index in indices) for row in rows]
            assert all(all(value for value in key) for key in keys)
            assert len(keys) == len(set(keys))


def test_independent_csv_stays_at_collection_root() -> None:
    item = manifest()["items"]["costs_2020.csv"]
    assert "part_of" not in item
    assert "derived_from" not in item
    headers, row_count = csv_shape(FIXTURE / "costs_2020.csv")
    assert row_count == item["quality"]["expected_rows"]
    assert headers == item["quality"]["expected_columns"]
