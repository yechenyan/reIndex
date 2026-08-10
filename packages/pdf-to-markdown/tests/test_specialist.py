from __future__ import annotations

from pathlib import Path

import pdf_to_markdown.specialist as specialist_module
from pdf_to_markdown.specialist import csv_to_markdown, plan_replacements, run_specialist
from pdf_to_markdown.specialist_pages import partition_replacements


def test_csv_to_markdown_escapes_cells(tmp_path: Path) -> None:
    source = tmp_path / "table.csv"
    source.write_text('A,B\n"x|y","two\nlines"\n', encoding="utf-8")
    markdown = csv_to_markdown(source)
    assert "x\\|y" in markdown
    assert "two<br>lines" in markdown


def test_plans_all_page_tables_in_visual_order(tmp_path: Path) -> None:
    upper_csv = tmp_path / "upper.csv"
    lower_csv = tmp_path / "lower.csv"
    upper_csv.write_text("A\nupper\n", encoding="utf-8")
    lower_csv.write_text("B\nlower\n", encoding="utf-8")
    candidates = [
        {"tableId": "source_1", "pages": [5], "spans": [[10, 20]], "pageBounds": [[0, 100]]},
        {"tableId": "source_2", "pages": [5], "spans": [[30, 40]], "pageBounds": [[0, 100]]},
    ]
    lower = {
        "parseTableId": "table_2",
        "outputPath": str(lower_csv),
        "tables": [{"page": 5, "bbox": [0, 50, 80, 90]}],
    }
    upper = {
        "parseTableId": "table_1",
        "outputPath": str(upper_csv),
        "tables": [{"page": 5, "bbox": [0, 10, 80, 40]}],
    }
    plans, used = plan_replacements(candidates, [lower, upper])
    assert len(plans) == 1
    assert plans[0]["spans"] == [[10, 20], [30, 40]]
    assert plans[0]["affectedTableIds"] == ["source_1", "source_2"]
    assert plans[0]["replacementMarkdown"].index("upper") < plans[0]["replacementMarkdown"].index("lower")
    assert used == {"table_1", "table_2"}


def test_three_specialist_tables_replace_four_liteparse_fragments(tmp_path: Path) -> None:
    candidates = [
        {"tableId": f"source_{index}", "pages": [8], "spans": [[index * 10, index * 10 + 5]],
         "pageBounds": [[0, 100]]}
        for index in range(1, 5)
    ]
    items = []
    for index, y in enumerate((10, 30, 50), start=1):
        source = tmp_path / f"table_{index}.csv"
        source.write_text(f"A\nvalue-{index}\n", encoding="utf-8")
        items.append({
            "parseTableId": f"table_{index}", "outputPath": str(source),
            "tables": [{"page": 8, "bbox": [0, y, 80, y + 10]}],
        })
    plans, used = plan_replacements(candidates, items)
    assert len(plans) == 1
    assert plans[0]["affectedTableIds"] == [f"source_{index}" for index in range(1, 5)]
    assert plans[0]["specialist"]["parseTableIds"] == [f"table_{index}" for index in range(1, 4)]
    assert used == {"table_1", "table_2", "table_3"}


def test_plan_leaves_table_on_other_page_unmatched(tmp_path: Path) -> None:
    source = tmp_path / "table.csv"
    source.write_text("A\nvalue\n", encoding="utf-8")
    candidates = [{"tableId": "source_1", "pages": [5], "spans": [[0, 10]], "pageBounds": [[0, 10]]}]
    item = {"parseTableId": "table_1", "outputPath": str(source), "tables": [{"page": 6}]}
    plans, used = plan_replacements(candidates, [item])
    assert plans == []
    assert used == set()


def test_plan_places_one_specialist_table_across_all_supplied_pages(tmp_path: Path) -> None:
    source = tmp_path / "table.csv"
    source.write_text("A\nvalue\n", encoding="utf-8")
    candidates = [
        {"tableId": f"source_{page}", "pages": [page], "spans": [[index * 10, index * 10 + 10]],
         "pageBounds": [[index * 10, index * 10 + 10]]}
        for index, page in enumerate((39, 40, 41, 42, 43))
    ]
    item = {
        "parseTableId": "table_1",
        "outputPath": str(source),
        "tables": [{"page": page} for page in (39, 40, 41, 42, 43)],
    }
    plans, used = plan_replacements(candidates, [item])
    assert len(plans) == 1
    assert plans[0]["affectedTableIds"] == [f"source_{page}" for page in (39, 40, 41, 42, 43)]
    assert used == {"table_1"}


def test_failed_table_blocks_connected_page_replacements(tmp_path: Path) -> None:
    accepted = [
        {"parseTableId": "span", "accepted": True, "outputPath": "span.csv",
         "tables": [{"page": 5}, {"page": 6}]},
        {"parseTableId": "same-page", "accepted": True, "outputPath": "same.csv",
         "tables": [{"page": 5}]},
        {"parseTableId": "safe", "accepted": True, "outputPath": "safe.csv",
         "tables": [{"page": 7}]},
    ]
    failed = {"parseTableId": "failed", "accepted": False, "outputPath": None,
              "tables": [{"page": 6}]}

    eligible, blocked, pages = partition_replacements([*accepted, failed])

    assert [item["parseTableId"] for item in eligible] == ["safe"]
    assert [item["parseTableId"] for item in blocked] == ["span", "same-page"]
    assert pages == [5, 6]


def test_specialist_exception_becomes_failed_result(tmp_path: Path, monkeypatch) -> None:
    candidate = {"tableId": "source_1", "route": "specialist", "status": "pending",
                 "pages": [5], "routeReasons": []}
    monkeypatch.setattr(specialist_module, "initialize_for_pages", lambda *_args: None)
    monkeypatch.setattr(specialist_module, "execute", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad")))

    result = run_specialist(
        tmp_path / "input.pdf", tmp_path / "project", [candidate], model="test", reasoning_effort="medium"
    )

    assert result["failed"] == ["workflow"]
    assert result["error"] == "ValueError: bad"
    assert candidate["status"] == "specialist_failed"
    assert candidate["routeReasons"] == ["ValueError: bad"]
