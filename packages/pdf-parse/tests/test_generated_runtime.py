import json
import sys
from types import SimpleNamespace

from pdf_parse import generated_runtime


def test_fixed_context_and_json_entry(tmp_path, monkeypatch, capsys):
    context_path = tmp_path / "context.json"
    context_path.write_text('{"pdfPath":"source.pdf"}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["parse.py", "--context", str(context_path)])
    assert generated_runtime.load_context() == {"pdfPath": "source.pdf"}
    generated_runtime.emit_table([["A"], ["B"]])
    assert json.loads(capsys.readouterr().out) == {"rows": [["A"], ["B"]]}


def test_fixed_liteparse_call(monkeypatch):
    captured = {}

    class FakeLiteParse:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def parse(self, path):
            captured["path"] = path
            return SimpleNamespace(pages=[SimpleNamespace(page_num=3)])

    monkeypatch.setattr(generated_runtime, "LiteParse", FakeLiteParse)
    page = generated_runtime.liteparse_page({"pdfPath": "source.pdf"}, 3)
    assert page.page_num == 3
    assert captured == {
        "ocr_enabled": False,
        "target_pages": "3",
        "extract_blocks": True,
        "emit_word_boxes": True,
        "extract_vector_graphics": True,
        "quiet": True,
        "path": "source.pdf",
    }
