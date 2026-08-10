from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pymupdf

from pdf_table_5.agent_context import finder_input, parser_images, parser_input
from pdf_table_5.api import initialize
from pdf_table_5.context import Context, Paths
from pdf_table_5.io import write_json
from pdf_table_5.parser_artifacts import apply as apply_artifacts
from pdf_table_5.parser_artifacts import decode_parser_payload, merge_repair_payload
from pdf_table_5.prompts_finder import finder_prompt
from pdf_table_5.prompts_parser import fixed_prefix, parser_prompt, repair_prompt
from pdf_table_5.taskPaperFindTables import run as find_tables
from pdf_table_5.taskPaperMergeTables import run as merge_tables


def test_finder_prompt_embeds_page_and_image_metadata() -> None:
    metadata = {
        "pageNumbering": "1-based",
        "coordinateSystem": {"origin": "top-left", "unit": "pt"},
        "pages": [{"page": 1, "width": 100, "height": 200, "overviewImagePixels": {"width": 133, "height": 267}}],
    }
    prompt = finder_prompt(finder_input(metadata, {"tableDpi": 216, "bboxMarginPt": 72}))
    assert '"overviewImagePixels":{"height":267,"width":133}' in prompt
    assert "taskPaperFindTables.json" not in prompt
    assert "repository discovery" in prompt
    assert "one visually continuous grid as one table" in prompt
    assert "Never create another table entry for only a subset" in prompt


def test_parser_prompt_embeds_compact_geometry_and_strategy_catalog(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    table = paths.table_dir("table_0000")
    table.mkdir(parents=True)
    paths.strategy.mkdir()
    write_json(paths.job, {"demand": {"inputPath": str(tmp_path / "source.pdf")}})
    geometry = table / "segment.json"
    write_json(geometry, {"words": [{"bbox": [1.234, 2, 3, 4], "text": "Cell", "block": 1, "line": 2, "word": 3}]})
    (paths.strategy / "strategy_grid.py").write_text('"""Applies when: grid"""\ndef extract_table(packet, segment):\n    return [], []\n')
    packet = {
        "parseTableId": "table_0000",
        "tables": [{"page": 1, "bbox": [0, 0, 10, 10], "geometry": "parse/tables/table_0000/segment.json",
                    "screenshot": "table.png", "contextScreenshot": "context.png"}],
    }
    prompt = parser_prompt(parser_input(Context(paths), packet))
    assert '[2.0,4.0,[[1.23,3.0,"Cell",1,2,3]]]' in prompt
    assert "strategy_grid.py" in prompt
    assert "lock_sample" not in prompt
    assert "wc -l" not in prompt
    assert "SKILL.md" not in prompt
    assert '"absolutePath"' in prompt
    assert '"wordCount":1' in prompt
    assert "from pdf_table_5.runtime_geometry import join_word_text, load_segments" in prompt
    assert 'words = segment["words"]' in prompt
    assert "never segment.words" in prompt
    assert "prefer join_word_text(words)" in prompt
    assert '"geometryHints"' in prompt
    assert '"evidenceEncoding"' in prompt
    assert "Never synthesize or pad an empty row" in prompt
    assert "python sample.py --table-json TABLE_JSON" in prompt
    assert "Return complete samplePy and parsePy strings" in prompt
    assert "preserve the existing\nsample values" in prompt
    assert "repeat the complete value in each CSV/sample row" in prompt
    assert "Visible cell borders override individual glyph x positions" in prompt
    assert "blank, `1`, `(0)`, blank" in prompt
    assert "add this rule immediately for each affected column" in prompt
    assert "Any raw sample value change is independently confirmed" in prompt
    assert "expected sample value != actual CSV value" in prompt
    assert "right-hand value is" in prompt
    assert "current parse.py output" in prompt
    assert '"runtimeGeometryLoader"' in prompt
    assert "TABLE BOUNDARY CHECK" in prompt
    assert "Never derive totalRows or sampled rows from a truncated crop" in prompt
    assert "Record the corrected boundary in summary.bboxes" in prompt


def test_yes_merge_is_deterministic_and_does_not_call_agent(tmp_path: Path, monkeypatch) -> None:
    paths = Paths(tmp_path)
    paths.helper.mkdir(parents=True)
    found = {
        "tables": [
            {"findTableId": "a", "preFindTableId": None, "page": 1, "bbox": [0, 0, 10, 10],
             "title": "First", "recommendedDpi": 216, "mergeWithPrevious": "no"},
            {"findTableId": "b", "preFindTableId": "a", "page": 2, "bbox": [0, 0, 10, 10],
             "title": "Second", "recommendedDpi": 216, "mergeWithPrevious": "yes"},
        ]
    }
    monkeypatch.setattr("pdf_table_5.taskPaperMergeTables.run_agent", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    merged, usage = merge_tables(Context(paths), found)
    assert usage == {}
    assert [[item["findTableId"] for item in group["tables"]] for group in merged["tables"]] == [["a", "b"]]


def test_finder_receives_inline_context_and_attached_page(tmp_path: Path, monkeypatch) -> None:
    source, project = tmp_path / "source.pdf", tmp_path / "project"
    document = pymupdf.open()
    page = document.new_page(width=100, height=200)
    page.insert_text((10, 20), "A B")
    document.save(source)
    initialize(source, project)
    captured = {}

    def fake_agent(context, role, prompt, **kwargs):
        captured.update(prompt=prompt, images=kwargs["images"], schema=kwargs["output_schema"])
        value = {"version": "pdf-table-5/find-table@1.0", "tables": []}
        return SimpleNamespace(payload={"findTableJson": json.dumps(value)}, token_usage={})

    monkeypatch.setattr("pdf_table_5.taskPaperFindTables.run_agent", fake_agent)
    found, _ = find_tables(Context(Paths(project)))
    metadata = json.loads((project / "parse/helper/taskPaperFindTables.json").read_text())
    assert found["tables"] == []
    assert len(captured["images"]) == 1
    assert metadata["pages"][0]["overviewImagePixels"] == {"width": 134, "height": 267}
    assert '"overviewImagePixels":{"height":267,"width":134}' in captured["prompt"]


def test_generated_parser_has_no_line_limit_and_sample_repairs_are_archived(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    table = paths.table_dir("table_0000")
    table.mkdir(parents=True)
    paths.strategy.mkdir()
    context = Context(paths)
    first = {
        "samplePy": "print('old')",
        "summary": {"skipped": False},
        "parsePy": "\n".join(["# generated"] * 350),
        "strategyFileName": "",
        "strategyPy": "",
    }
    apply_artifacts(context, "table_0000", first)
    second = {**first, "samplePy": "print('new')"}
    apply_artifacts(context, "table_0000", second, sample_archive=1)
    assert len((table / "parse.py").read_text().splitlines()) == 350
    assert (table / "sample1.py").is_file()
    assert not (table / "sample.lock.json").exists()


def test_repair_prompt_keeps_fixed_cache_prefix_and_sends_dynamic_data_last() -> None:
    context = {
        "runtimePaths": {"tableDir": "/p/t", "projectRoot": "/p"},
        "runtimeClassification": {"imageTable": False},
        "geometryHints": {"segments": [{"lineCount": 2}]},
    }
    artifacts = {"samplePy": "", "summary": {}, "parsePy": "", "strategyFileName": "", "strategyPy": ""}
    initial = parser_prompt(context)
    fallback = repair_prompt(context, artifacts, {"errors": ["x"]}, 2, 3, include_full_context=True)
    resumed = repair_prompt(context, artifacts, {"errors": ["x"]}, 2, 3, include_full_context=False)
    assert initial.startswith(fixed_prefix())
    assert "Read the attached table image directly with your own visual understanding" in initial
    assert "An image table must use skip mode" in initial
    assert "higher-DPI image" in initial
    assert fallback.startswith(fixed_prefix())
    assert resumed.startswith("PDF-TABLE-5 RESUMED SESSION DELTA")
    assert fixed_prefix() not in resumed
    assert resumed.index('"attempt":2') > resumed.index("DYNAMIC REQUEST")
    assert '"lineCount":2' in resumed
    assert len(resumed) < len(fallback)


def test_repair_patch_preserves_null_artifacts() -> None:
    current = {
        "samplePy": "print('old')", "summary": {"imageTable": False}, "parsePy": "old",
        "strategyFileName": "", "strategyPy": "",
    }
    payload = {
        "baseRevision": 4, "diagnosis": "parser only",
        "changes": {"samplePy": None, "summary": None, "parsePy": "new",
                    "strategyFileName": None, "strategyPy": None},
    }
    merged = merge_repair_payload(current, payload, revision=4, image_table=False)
    assert merged["parsePy"] == "new"
    assert merged["samplePy"] == current["samplePy"]
    sample_fix = {
        "baseRevision": 4, "diagnosis": "sample only",
        "changes": {"samplePy": "print('new')", "summary": None, "parsePy": None,
                    "strategyFileName": None, "strategyPy": None},
    }
    repaired = merge_repair_payload(current, sample_fix, revision=4, image_table=False)
    assert repaired["samplePy"] == "print('new')"
    assert repaired["parsePy"] == "old"


def test_parser_payload_preserves_sample_program() -> None:
    payload = {
        "samplePy": "print('{}')",
        "summary": {}, "parsePy": "pass", "strategyFileName": "", "strategyPy": "",
    }
    result = decode_parser_payload(payload, image_table=False)
    assert result["samplePy"] == "print('{}')"


def test_parser_images_attach_only_crops_by_default(tmp_path: Path) -> None:
    packet = {"tables": [
        {"screenshot": "a.png", "contextScreenshot": "a-context.png"},
        {"screenshot": "b.png", "contextScreenshot": "b-context.png"},
    ]}
    context = Context(Paths(tmp_path))
    assert [path.name for path in parser_images(context, packet)] == ["a.png", "b.png"]
    assert [path.name for path in parser_images(context, packet, include_context=True)] == [
        "a.png", "a-context.png", "b.png", "b-context.png",
    ]
