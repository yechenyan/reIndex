import json
import shutil
from pathlib import Path

import yaml
from reindex_cli.cli import main


def output(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


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
    fixture = Path(__file__).resolve().parents[1] / "testbase" / "test2-generage"
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
