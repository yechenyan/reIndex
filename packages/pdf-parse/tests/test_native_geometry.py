from types import SimpleNamespace

from pdf_parse.io_utils import atomic_json
from pdf_parse.native_geometry import page_geometry, scoped_geometry
from pdf_parse.paths import ProjectPaths


def test_native_page_keeps_object_hierarchy_and_direct_word_coordinates():
    word = SimpleNamespace(text="0 €", x=10, y=20, width=6, height=4)
    item = SimpleNamespace(
        text="0 €", x=10, y=20, width=6, height=4, rotation=0, words=[word]
    )
    line = SimpleNamespace(
        x1=5, y1=22, x2=30, y2=22, stroke=True, stroke_width=1,
        stroke_color="#000", fill=False, fill_color=None,
    )
    graphics = SimpleNamespace(lines=[line], shapes=[])
    block = SimpleNamespace(kind="text", text="0 €", bbox=None, header=None, rows=None)
    page = SimpleNamespace(
        page_num=1, width=100, height=200, text_items=[item],
        vector_graphics=graphics, blocks=[block],
    )

    value = page_geometry(page)

    assert value["text_items"][0]["words"][0] == {
        "text": "0 €", "x": 10, "y": 20, "width": 6, "height": 4
    }
    assert value["vector_graphics"]["lines"][0]["x2"] == 30


def test_scope_is_mechanical_and_revision_is_stable(tmp_path):
    paths = ProjectPaths(tmp_path)
    paths.create_directories()
    raw = {
        "page_num": 1,
        "width": 100,
        "height": 200,
        "text_items": [
            {"index": 0, "text": "in", "x": 10, "y": 10, "width": 5, "height": 5,
             "rotation": 0, "words": []},
            {"index": 1, "text": "out", "x": 80, "y": 80, "width": 5, "height": 5,
             "rotation": 0, "words": []},
        ],
        "vector_graphics": {
            "lines": [{"index": 0, "x1": 0, "y1": 12, "x2": 40, "y2": 12}],
            "shapes": [],
        },
        "blocks": [],
    }
    atomic_json(paths.helper / "native-geometry" / "page-0001.json", raw)

    first = scoped_geometry(paths, [(1, [5, 5, 20, 20])])
    second = scoped_geometry(paths, [(1, [5, 5, 20, 20])])

    schema = first["record_schemas"]["text_item"]
    item = dict(zip(schema, first["pages"][0]["text_items"][0]))
    assert item["text"] == "in"
    assert len(first["pages"][0]["vector_graphics"]["lines"]) == 1
    assert first["revision"] == second["revision"]
