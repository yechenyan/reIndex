from __future__ import annotations

from types import SimpleNamespace

import pymupdf

from pdf_to_markdown.liteparse_runner import (
    DEFAULT_DPI,
    MAX_RENDER_PIXELS,
    MAX_RENDER_SIDE,
    bounded_dpi,
    parse_pdf,
)


def test_parse_pdf_extracts_images_and_uses_relative_asset_paths(tmp_path, monkeypatch) -> None:
    captured = {}

    class FakeLiteParse:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def parse(self, _pdf):
            page = SimpleNamespace(
                page_num=1, width=100, height=200, markdown="![](img_p1_1.jpg)",
                text_items=[], complexity=None, vector_graphics=None,
            )
            return SimpleNamespace(
                text="![](img_p1_1.jpg)", pages=[page],
                images=[SimpleNamespace(name="img_p1_1.jpg")],
            )

    monkeypatch.setattr("pdf_to_markdown.liteparse_runner.LiteParse", FakeLiteParse)
    monkeypatch.setattr("pdf_to_markdown.liteparse_runner.bounded_dpi", lambda _pdf: 120.0)
    assets = tmp_path / "assets"
    result = parse_pdf(tmp_path / "input.pdf", image_output_dir=assets)

    assert captured["extract_images"] is True
    assert captured["dpi"] == 120.0
    assert captured["image_output_dir"] == assets
    assert assets.is_dir()
    assert result["markdown"] == "![](assets/img_p1_1.jpg)"
    assert result["pages"][0]["markdown"] == "![](assets/img_p1_1.jpg)"
    assert result["renderDpi"] == 120.0


def test_bounded_dpi_keeps_a4_at_default_and_caps_oversized_page(tmp_path) -> None:
    normal = tmp_path / "normal.pdf"
    document = pymupdf.open()
    document.new_page(width=595.32, height=841.92)
    document.save(normal)
    document.close()
    assert bounded_dpi(normal) == DEFAULT_DPI

    oversized = tmp_path / "oversized.pdf"
    document = pymupdf.open()
    document.new_page(width=4953.18, height=3499.76)
    document.save(oversized)
    document.close()
    dpi = bounded_dpi(oversized)
    assert max(4953.18, 3499.76) * dpi / 72 <= MAX_RENDER_SIDE
    assert 4953.18 * 3499.76 * (dpi / 72) ** 2 <= MAX_RENDER_PIXELS
