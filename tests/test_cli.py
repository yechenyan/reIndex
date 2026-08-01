import json
import shutil
from pathlib import Path

import yaml
from reindex_cli.cli import main


def output(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def test_create_inspect_scan_and_check(tmp_path: Path, capsys) -> None:
    root = tmp_path / "notes"
    root.mkdir()
    (root / "guide.md").write_text("# Guide\n\nUseful text.\n", encoding="utf-8")
    assert main(["create", str(root)]) == 0
    collection = output(capsys)
    assert collection["status"] == "ready"
    assert collection["created"] is True
    collection_id = collection["collection_id"]
    assert main(["create", str(root)]) == 0
    reused = output(capsys)
    assert reused["created"] is False
    assert reused["collection_id"] == collection_id
    assert main(["inspect", str(root / "guide.md")]) == 0
    inspected = output(capsys)
    assert inspected["inputs"] == {"md": 1}
    assert inspected["items"][0]["path"] == "guide.md"
    assert inspected["items"][0]["change"] == "new"
    assert not (root / ".rei" / "build.json").exists()
    assert main(["scan", str(root)]) == 0
    scan = output(capsys)
    assert scan["nodes"] == 2
    assert len(scan["changes"]["added"]) == 2
    assert scan["review"]["new_nodes"] == scan["changes"]["added"]
    assert scan["warnings"] == []
    assert scan["warning_count"] == 0
    package = Path(scan["package"])
    assert package.name.startswith(f"{collection_id}--notes")
    assert (package / "guide.node.md").is_file()
    assert (package / "guide.md").is_file()
    assert main(["check", str(root)]) == 0
    assert output(capsys)["status"] == "valid"


def test_check_detects_new_input(tmp_path: Path, capsys) -> None:
    root = tmp_path / "stale-new"
    root.mkdir()
    (root / "one.md").write_text("# One\n", encoding="utf-8")
    assert main(["create", str(root)]) == 0
    output(capsys)
    assert main(["scan", str(root)]) == 0
    output(capsys)
    (root / "two.md").write_text("# Two\n", encoding="utf-8")
    assert main(["check", str(root)]) == 0
    result = output(capsys)
    assert result["status"] == "stale"
    assert result["stale_inputs"] is True
    assert result["stale"]["new_inputs"] == ["two.md"]


def test_check_ignores_new_file_below_ignored_directory(tmp_path: Path, capsys) -> None:
    root = tmp_path / "ignored-new"
    (root / "scratch").mkdir(parents=True)
    (root / "one.md").write_text("# One\n", encoding="utf-8")
    (root / "reIndex.md").write_text(
        '---\nspec: "reindex/input@1.0"\nitems:\n  "scratch":\n    ignore: true\n---\n',
        encoding="utf-8",
    )
    assert main(["create", str(root)]) == 0
    output(capsys)
    assert main(["scan", str(root)]) == 0
    output(capsys)
    (root / "scratch" / "temporary.md").write_text("# Temporary\n", encoding="utf-8")
    assert main(["check", str(root)]) == 0
    result = output(capsys)
    assert result["status"] == "valid"
    assert result["stale_inputs"] is False


def test_agent_body_survives_rescan(tmp_path: Path, capsys) -> None:
    root = tmp_path / "cards"
    root.mkdir()
    (root / "note.md").write_text("# Note\n\nSource text.\n", encoding="utf-8")
    assert main(["create", str(root)]) == 0
    output(capsys)
    assert main(["scan", str(root)]) == 0
    scan = output(capsys)
    package = Path(scan["package"])
    card = next(
        path for path in package.glob("*.node.md") if path.name != "index.node.md"
    )
    metadata, body = _card(card)
    curated = body + "\n## Agent note\n\nReviewed content.\n"
    card.write_text(_render(metadata, curated), encoding="utf-8", newline="\n")
    assert main(["check", str(root)]) == 0
    assert output(capsys)["agent_modified_cards"] == 1
    assert main(["scan", str(root)]) == 0
    output(capsys)
    assert "Reviewed content." in card.read_text(encoding="utf-8")


def test_check_rejects_machine_metadata_edits(tmp_path: Path, capsys) -> None:
    root = tmp_path / "machine-owned"
    root.mkdir()
    (root / "note.md").write_text("# Note\n", encoding="utf-8")
    assert main(["create", str(root)]) == 0
    output(capsys)
    assert main(["scan", str(root)]) == 0
    package = Path(output(capsys)["package"])
    card = next(
        path for path in package.glob("*.node.md") if path.name != "index.node.md"
    )
    metadata, body = _card(card)
    metadata["title"] = "Agent changed machine metadata"
    card.write_text(_render(metadata, body), encoding="utf-8", newline="\n")
    assert main(["check", str(root)]) == 1
    assert "CLI-owned Node metadata changed" in capsys.readouterr().err


def test_partial_scans_accumulate_collection_content(tmp_path: Path, capsys) -> None:
    root = tmp_path / "partial"
    (root / "a").mkdir(parents=True)
    (root / "b").mkdir()
    (root / "a" / "one.md").write_text("# One\n", encoding="utf-8")
    (root / "b" / "two.md").write_text("# Two\n", encoding="utf-8")
    assert main(["create", str(root)]) == 0
    output(capsys)
    assert main(["scan", str(root / "a")]) == 0
    assert output(capsys)["nodes"] == 3
    assert main(["scan", str(root / "b")]) == 0
    assert output(capsys)["nodes"] == 5


def test_unique_hash_rename_keeps_node_identity(tmp_path: Path, capsys) -> None:
    root = tmp_path / "rename"
    root.mkdir()
    old = root / "old.md"
    old.write_text("# Stable\n", encoding="utf-8")
    assert main(["create", str(root)]) == 0
    output(capsys)
    assert main(["scan", str(root)]) == 0
    package = Path(output(capsys)["package"])
    old_card = next(
        path for path in package.glob("*.node.md") if path.name != "index.node.md"
    )
    old_id = _card(old_card)[0]["id"]
    old.rename(root / "new.md")
    assert main(["scan", str(root)]) == 0
    package = Path(output(capsys)["package"])
    new_card = next(
        path for path in package.glob("*.node.md") if path.name != "index.node.md"
    )
    assert _card(new_card)[0]["id"] == old_id


def test_supplied_parse_value_is_rejected(tmp_path: Path, capsys) -> None:
    root = tmp_path / "invalid"
    root.mkdir()
    (root / "report.pdf").write_bytes(b"not needed for manifest validation")
    (root / "reIndex.md").write_text(
        '---\nspec: "reindex/input@1.0"\nitems:\n  "report.pdf":\n'
        "    parse:\n      tables: supplied\n---\n",
        encoding="utf-8",
    )
    assert main(["create", str(root)]) == 0
    output(capsys)
    assert main(["inspect", str(root)]) == 1
    assert "auto or off" in capsys.readouterr().err


def test_inspect_rejects_relation_pages_past_pdf_end(tmp_path: Path, capsys) -> None:
    root = tmp_path / "bad-pages"
    root.mkdir()
    fixture = Path(__file__).resolve().parents[1] / "testbase" / "test2"
    pdf_name = "report.pdf"
    shutil.copyfile(
        fixture
        / "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf",
        root / pdf_name,
    )
    (root / "table.csv").write_text("name,value\na,1\n", encoding="utf-8")
    (root / "reIndex.md").write_text(
        '---\nspec: "reindex/input@1.0"\nitems:\n  "table.csv":\n'
        f'    part_of: "{pdf_name}"\n    pages: [6, 6]\n---\n',
        encoding="utf-8",
    )
    assert main(["create", str(root)]) == 0
    output(capsys)
    assert main(["inspect", str(root)]) == 1
    assert "pages exceed relation target page count" in capsys.readouterr().err


def test_part_of_turns_non_pdf_target_into_document_group(
    tmp_path: Path, capsys
) -> None:
    root = tmp_path / "non-pdf-relation"
    root.mkdir()
    (root / "report.md").write_text("# Report\n\nNarrative.\n", encoding="utf-8")
    (root / "table.csv").write_text("name,value\na,1\n", encoding="utf-8")
    (root / "reIndex.md").write_text(
        '---\nspec: "reindex/input@1.0"\nitems:\n  "table.csv":\n'
        '    part_of: "report.md"\n---\n',
        encoding="utf-8",
    )
    assert main(["create", str(root)]) == 0
    output(capsys)
    assert main(["scan", str(root)]) == 0
    package = Path(output(capsys)["package"])
    cards = [_card(path)[0] for path in package.rglob("*.node.md")]
    assert [card["kind"] for card in cards].count("group") == 2
    assert [card["kind"] for card in cards].count("text") == 1
    assert [card["kind"] for card in cards].count("table") == 1


def _card(path: Path) -> tuple[dict, str]:
    _empty, frontmatter, body = path.read_text(encoding="utf-8").split("---", 2)
    return yaml.safe_load(frontmatter), body.lstrip("\n")


def _render(metadata: dict, body: str) -> str:
    frontmatter = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).rstrip()
    return f"---\n{frontmatter}\n---\n{body}"
