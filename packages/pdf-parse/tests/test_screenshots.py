from pdf_parse.screenshots import bounded_dpi


PARAMS = {
    "screenshots": {
        "minDpi": 72,
        "maxDpi": 300,
        "maxImageSide": 4096,
        "maxImagePixels": 12_000_000,
    }
}


def test_requested_dpi_is_project_bounded():
    assert bounded_dpi(50, 595, 842, PARAMS) == 72
    assert bounded_dpi(600, 595, 842, PARAMS) == 300


def test_large_page_dpi_is_reduced_by_pixel_limit():
    dpi = bounded_dpi(300, 2000, 1000, PARAMS)
    assert 120 < dpi < 150
