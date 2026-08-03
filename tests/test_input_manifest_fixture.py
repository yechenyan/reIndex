from pathlib import Path, PurePosixPath

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "testbase" / "test2-generage"
MANIFEST = FIXTURE / "reIndex.md"
PDF_NAME = "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
AGGREGATE = "00005--aggregierte-10-jahresplanung-untere-netzebenen.csv"
MEASURES = "00006--massnahmenplan-aller-spannungsebenen.csv"


def manifest() -> dict:
    _, frontmatter, _ = MANIFEST.read_text(encoding="utf-8").split("---", 2)
    return yaml.safe_load(frontmatter)


def test_input_manifest_references_safe_existing_items() -> None:
    value = manifest()
    assert value["spec"] == "reindex/input@1.0"
    assert "collection" not in value
    assert FIXTURE.name == "test2-generage"
    items = value["items"]
    assert set(items) == {
        PDF_NAME,
        AGGREGATE,
        MEASURES,
        "costs_2020.csv",
    }
    for relative in items:
        path = PurePosixPath(relative)
        assert not path.is_absolute() and ".." not in path.parts
        assert (FIXTURE / relative).is_file()
    for item in items.values():
        target = item.get("part_of") or item.get("derived_from")
        if target:
            assert target in items


def test_external_tables_declare_pdf_relationship() -> None:
    items = manifest()["items"]
    assert items[PDF_NAME]["parse"]["tables"] == "off"
    for name in (AGGREGATE, MEASURES):
        item = items[name]
        assert item["part_of"] == PDF_NAME
        assert item["pages"] == [5, 5]
        assert "quality" not in item


def test_independent_csv_stays_at_collection_root() -> None:
    item = manifest()["items"]["costs_2020.csv"]
    assert "part_of" not in item
    assert "derived_from" not in item
    assert "quality" not in item
