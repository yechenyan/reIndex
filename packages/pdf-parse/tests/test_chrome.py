from pdf_parse.chrome import mark_repeated_page_chrome


def block(block_id, kind, bbox):
    return {
        "blockId": block_id,
        "liteParseType": kind,
        "bbox": bbox,
        "ignored": False,
        "ignoredReason": None,
        "needsAgent": True,
    }


def test_repeated_header_is_ignored_but_body_figure_is_not():
    pages = [
        {
            "page": 1,
            "heightPt": 800,
            "blocks": [block("logo-1", "figure", [320, 30, 200, 60])],
        },
        {
            "page": 2,
            "heightPt": 800,
            "blocks": [
                block("logo-2", "figure", [320, 30, 200, 60]),
                block("body", "figure", [70, 150, 450, 400]),
            ],
        },
    ]
    mark_repeated_page_chrome(pages)
    assert pages[0]["blocks"][0]["ignoredReason"] == "repeated_page_chrome"
    assert pages[1]["blocks"][0]["needsAgent"] is False
    assert pages[1]["blocks"][1]["ignored"] is False
