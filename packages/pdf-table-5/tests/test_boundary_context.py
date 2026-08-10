from __future__ import annotations

from pathlib import Path

from pdf_table_5.agent_context import parser_images, parser_input
from pdf_table_5.context import Context, Paths
from pdf_table_5.io import write_json


def test_large_continued_table_inlines_only_boundary_segments(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    table = paths.table_dir("table_0000")
    table.mkdir(parents=True)
    paths.strategy.mkdir()
    source = tmp_path / "source.pdf"
    source.write_bytes(b"pdf")
    write_json(paths.job, {"demand": {"inputPath": str(source)}})
    segments = []
    for index in range(4):
        geometry = table / f"segment-{index}.json"
        write_json(
            geometry,
            {"words": [{"bbox": [1, index + 1, 2, index + 2], "text": f"page-{index + 1}"}]},
        )
        segments.append(
            {
                "page": index + 1,
                "bbox": [0, 0, 10, 10],
                "geometry": str(geometry.relative_to(tmp_path)),
                "screenshot": f"table-{index}.png",
                "contextScreenshot": f"context-{index}.png",
            }
        )
    packet = {"parseTableId": "table_0000", "tables": segments}
    context = Context(paths)
    value = parser_input(context, packet)

    assert value["evidenceMode"] == {
        "mode": "boundary", "segmentCount": 4, "fullEvidenceIndexes": [0, 3],
        "allSegmentsLoadAtRuntime": True,
    }
    assert [item["page"] for item in value["evidence"]] == [1, 4]
    assert len(value["runtimePaths"]["geometryFiles"]) == 4
    assert [path.name for path in parser_images(context, packet)] == ["table-0.png", "table-3.png"]
