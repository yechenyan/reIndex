from pdf_parse.prompts import load_prompt


def test_classifier_requires_visual_coverage_without_runtime_grid_repair():
    prompt = load_prompt("classify.md")
    assert "visual coverage audit" in prompt
    assert "exactly once" in prompt
    assert "empty single-cell input area" in prompt
    assert "will not repair" in prompt


def test_table_prompt_defines_native_geometry_contract():
    prompt = load_prompt("table.md")
    assert "page.text_items" in prompt
    assert "page.vector_graphics.lines/shapes" in prompt
    assert "page.blocks" in prompt
    assert "not under `word.bbox`" in prompt
    assert "not subscriptable" in prompt
    assert "enumerate(block.rows)" in prompt
    assert "{{RUNTIME_CONTEXT}}" in prompt
    assert "geometryRevisionUsed" in prompt
    assert "table is ruled or unruled" in prompt


def test_repair_prompt_does_not_require_minimal_edits():
    prompt = load_prompt("repair.md")
    assert "liteparse_page(context, page_number)" in prompt
    assert "does not resend the screenshot" in prompt
    assert "inspect all supplied errors together" in prompt
    assert "smallest possible edit" not in prompt
    assert "minimally" not in prompt
    assert "Minimal physical-row" not in prompt
