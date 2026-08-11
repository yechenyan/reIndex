from pathlib import Path

from reindex_cli.manifest.models import ItemConfig
from reindex_cli.parsers.csv_parser import parse_csv
from reindex_cli.parsers.docling_structure import extract_structure
from reindex_cli.parsers.markdown import parse_markdown
from reindex_cli.package.cards import parse_card, render_card
from reindex_cli.pipeline.models import SourceItem


class _Prov:
    def __init__(self, page_no: int):
        self.page_no = page_no


SectionHeaderItem = type("SectionHeaderItem", (), {})
TextItem = type("TextItem", (), {})
PictureItem = type("PictureItem", (), {})


class _Document:
    def __init__(self, items):
        self.items = items

    def iterate_items(self):
        yield from self.items


def _item(kind, text: str = "", page: int = 1):
    value = kind()
    value.text = text
    value.prov = [_Prov(page)]
    return value


def _source(path: Path) -> SourceItem:
    return SourceItem(path.name, path, "a" * 64, "text/plain", ItemConfig(path.name))


def test_csv_card_contains_compact_deterministic_field_statistics(
    tmp_path: Path,
) -> None:
    path = tmp_path / "values.csv"
    path.write_text("name,value\na,1\nb,\nc,3\n", encoding="utf-8")
    node = parse_csv(_source(path))[0]
    assert node.table["profile"] == [
        {
            "name": "name",
            "type": "string",
            "non_empty_count": 3,
            "missing_count": 0,
            "missing_rate": 0.0,
            "unique_count": 3,
        },
        {
            "name": "value",
            "type": "integer",
            "non_empty_count": 2,
            "missing_count": 1,
            "missing_rate": 1 / 3,
            "unique_count": 2,
            "min": 1,
            "max": 3,
        },
    ]
    assert "| value | integer | 2 | 1 | 33.3% | 2 | 1 | 3 |" in node.body
    assert "## Preview" in node.body


def test_markdown_headings_define_nodes_without_agent_splitting(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    path.write_text(
        "# Report\n\n## Scope\n\nScope text.\n\n## Data\n\nData text.\n",
        encoding="utf-8",
    )
    nodes = parse_markdown(_source(path))
    assert [node.kind for node in nodes] == ["group", "text", "text"]
    assert [node.title for node in nodes[1:]] == ["Scope", "Data"]
    assert nodes[1].context["section_path"] == ["Report", "Scope"]
    assert "`Report` > `Scope`" in nodes[1].body


def test_card_frontmatter_allows_literal_delimiter_in_a_value(tmp_path: Path) -> None:
    path = tmp_path / "card.node.md"
    path.write_bytes(render_card({"title": "A --- B"}, "Body"))
    metadata, body = parse_card(path)
    assert metadata == {"title": "A --- B"}
    assert body == "Body"


def test_docling_structure_uses_headings_and_nearby_text() -> None:
    contents = _item(SectionHeaderItem, "CONTENTS")
    contents_text = _item(TextItem, "Section list")
    heading = _item(SectionHeaderItem, "A. Scope", page=2)
    before = _item(TextItem, "Text before the figure.", page=2)
    picture = _item(PictureItem, page=2)
    after = _item(TextItem, "Text after the figure.", page=2)
    document = _Document(
        [
            (contents, 1),
            (contents_text, 1),
            (heading, 1),
            (before, 1),
            (picture, 1),
            (after, 1),
        ]
    )
    chunks, contexts = extract_structure(document, set())
    assert [chunk.title for chunk in chunks] == ["A. Scope"]
    assert chunks[0].pages == (2, 2)
    assert contexts[id(picture)]["section_path"] == ["A. Scope"]
    assert contexts[id(picture)]["nearby_text"] == (
        "Text before the figure. Text after the figure."
    )
