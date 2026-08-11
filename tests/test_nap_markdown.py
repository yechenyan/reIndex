from pathlib import Path

from reindex_cli.manifest.models import ItemConfig
from reindex_cli.parsers.nap_markdown import is_nap_markdown, parse_nap_markdown
from reindex_cli.parsers.registry import parse_item
from reindex_cli.pipeline.discovery import discover
from reindex_cli.pipeline.models import SourceItem
from reindex_cli.manifest.models import InputManifest


def _source(path: Path) -> SourceItem:
    return SourceItem(
        "operator/report-pdf-to-markdown-run/output.md",
        path,
        "a" * 64,
        "text/markdown",
        ItemConfig("operator/report-pdf-to-markdown-run/output.md"),
    )


def test_nap_parser_emits_text_and_structured_tables_without_images(
    tmp_path: Path,
) -> None:
    path = tmp_path / "report-pdf-to-markdown-run" / "output.md"
    path.parent.mkdir()
    path.write_text(
        "# Netzausbauplan 2024\n\nOverview.\n\n![](assets/map.png)\n\n"
        "## Investments\n\n| ID | Value | Value |\n| --- | --- | --- |\n"
        "| 1 | A\\|B | 10 |\n| 2 | C | 20 |\n",
        encoding="utf-8",
    )
    nodes = parse_nap_markdown(_source(path))
    table = next(node for node in nodes if node.kind == "table")
    text = next(node for node in nodes if node.kind == "text")

    assert [node.kind for node in nodes] == ["group", "text", "table"]
    assert nodes[0].title == "Netzausbauplan 2024"
    assert text.parent_key == nodes[0].logical_key
    assert "assets/map.png" not in text.content.decode()
    assert table.table["row_count"] == 2
    assert [column["name"] for column in table.table["columns"]] == [
        "ID",
        "Value",
        "Value (2)",
    ]
    assert "1,A|B,10\n" in table.content.decode()


def test_registry_routes_only_pdf_to_markdown_output_files(tmp_path: Path) -> None:
    path = tmp_path / "report-pdf-to-markdown-run" / "output.md"
    path.parent.mkdir()
    path.write_text("| A |\n| --- |\n| value |\n", encoding="utf-8")
    item = _source(path)

    assert is_nap_markdown(item)
    assert [node.kind for node in parse_item(item, set())] == ["group", "table"]


def test_derived_nap_nodes_keep_the_pdf_as_their_source(tmp_path: Path) -> None:
    path = tmp_path / ".nap-markdown.md"
    path.write_text("| A |\n| --- |\n| value |\n", encoding="utf-8")
    item = SourceItem(
        "documents/output.md", path, "a" * 64, "text/markdown",
        ItemConfig("documents/output.md", derived_from="sources/report.pdf"),
    )

    nodes = parse_nap_markdown(item)

    assert is_nap_markdown(item)
    assert all(node.source_path == "sources/report.pdf" for node in nodes)
    assert all(node.source_sha256 is None for node in nodes)


def test_discovery_keeps_only_the_nap_markdown_input(tmp_path: Path) -> None:
    source_dir = tmp_path / "operator"
    run = source_dir / "report-pdf-to-markdown-run"
    (run / "assets").mkdir(parents=True)
    (run / "work").mkdir()
    (source_dir / "report.pdf").write_bytes(b"source")
    (run / "output.md").write_text("Narrative", encoding="utf-8")
    (run / "assets" / "map.png").write_bytes(b"image")
    (run / "work" / "report.json").write_text("{}", encoding="utf-8")
    manifest = InputManifest(None, None, "NAP", "NAP inputs", {})

    assert list(discover(tmp_path, manifest)) == [
        "operator/report-pdf-to-markdown-run/output.md"
    ]


def test_disabled_pdf_is_retained_as_a_raw_file_node(tmp_path: Path) -> None:
    path = tmp_path / "report.pdf"
    path.write_bytes(b"not parsed")
    item = SourceItem(
        "report.pdf", path, "a" * 64, "application/pdf",
        ItemConfig("report.pdf", parse={"text": "off", "images": "off", "tables": "off"}),
    )

    node = parse_item(item, set())[0]

    assert node.kind == "file"
    assert node.source_path == "report.pdf"
