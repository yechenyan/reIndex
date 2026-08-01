import json
import mimetypes
import shutil
from pathlib import Path
from uuid import UUID, uuid5

import yaml
from reindex_cli.collection import resolve_collection
from reindex_cli.pipeline.runner import check_collection, inspect_collection
from reindex_server.domain import Resource
from reindex_server.package_import import load_package
from reindex_server.storage import FileStore

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "testbase" / "test2"


def test_test2_generated_package_is_current() -> None:
    context = resolve_collection(FIXTURE)
    inspected = inspect_collection(context)
    assert inspected["summary"] == {
        "selected": 4,
        "ignored": 0,
        "new": 0,
        "changed": 0,
        "removed": 0,
    }
    profiles = {item["path"]: item for item in inspected["items"]}
    assert (
        profiles[
            "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
        ]["profile"]["page_count"]
        == 5
    )
    assert (
        profiles["00006--massnahmenplan-aller-spannungsebenen.csv"]["profile"][
            "row_count"
        ]
        == 52
    )
    assert profiles["00006--massnahmenplan-aller-spannungsebenen.csv"]["relation"] == {
        "type": "part_of",
        "target": "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf",
        "target_valid": True,
        "pages": [5, 5],
        "target_page_count": 5,
        "pages_valid": True,
    }
    result = check_collection(context)
    assert result["status"] == "valid"
    assert result["nodes"] == 7
    build = json.loads((FIXTURE / ".rei" / "build.json").read_text(encoding="utf-8"))
    assert build["item_paths"] == [
        "00005--aggregierte-10-jahresplanung-untere-netzebenen.csv",
        "00006--massnahmenplan-aller-spannungsebenen.csv",
        "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf",
        "costs_2020.csv",
    ]
    assert all("supplied" not in warning for warning in build["warnings"])
    assert (context.output_dir / "technology-costs-2020.csv").is_file()
    assert (context.output_dir / "technology-costs-2020.node.md").is_file()
    assert not list(context.output_dir.glob("[0-9][0-9][0-9][0-9][0-9]--technology-*"))
    cards = [_metadata(path) for path in context.output_dir.rglob("*.node.md")]
    assert [card["kind"] for card in cards].count("table") == 3
    table_profiles = {
        card["title"]: (card["table"]["row_count"], _column_names(card))
        for card in cards
        if card["kind"] == "table"
    }
    assert table_profiles["Aggregierte 10-Jahresplanung der unteren Netzebenen"] == (
        24,
        ["Netzebene", "Investitionsart", "Betrag_EUR"],
    )
    assert table_profiles["Maßnahmenplan aller Spannungsebenen für zehn Jahre"][0] == 52
    assert table_profiles["Technology costs 2020"][0] == 1091
    pdf_tables = [
        card
        for card in cards
        if card["kind"] == "table" and card["source"]["uri"].endswith("anhang_pdf.pdf")
    ]
    assert len(pdf_tables) == 2
    assert all(card["source"]["locator"]["pages"] == [5, 5] for card in pdf_tables)
    assert all(card["assets"][0]["role"] == "visual_reference" for card in pdf_tables)
    pdf_texts = [
        card
        for card in cards
        if card["kind"] == "text" and card["source"]["uri"].endswith("anhang_pdf.pdf")
    ]
    assert len(pdf_texts) == 1
    assert pdf_texts[0]["title"] == "Document text"
    assert all(card["source"]["locator"]["pages"][1] <= 4 for card in pdf_texts)


def test_test2_package_loads_with_server_importer(tmp_path: Path) -> None:
    context = resolve_collection(FIXTURE)
    store = FileStore(tmp_path / "objects")
    build = json.loads((FIXTURE / ".rei" / "build.json").read_text(encoding="utf-8"))
    existing = {}
    for relative in build["item_paths"]:
        source = FIXTURE / relative
        stored = store.put_file(source)
        resource = Resource(
            str(uuid5(UUID(context.collection_id), f"raw:{relative}")),
            context.collection_id,
            "raw",
            relative,
            source.name,
            stored.sha256,
            stored.byte_size,
            mimetypes.guess_type(source.name)[0] or "application/octet-stream",
            stored.object_key,
        )
        existing[("raw", relative)] = resource
    unpacked = tmp_path / "unpacked"
    unpacked.mkdir()
    shutil.copytree(context.output_dir, unpacked / context.output_dir.name)
    snapshot = load_package(unpacked, context.collection_id, store, existing)
    assert len(snapshot.nodes) == 7
    assert len([node for node in snapshot.nodes.values() if node.kind == "table"]) == 3


def _metadata(path: Path) -> dict:
    _empty, frontmatter, _body = path.read_text(encoding="utf-8").split("---", 2)
    return yaml.safe_load(frontmatter)


def _column_names(card: dict) -> list[str]:
    return [column["name"] for column in card["table"]["columns"]]
