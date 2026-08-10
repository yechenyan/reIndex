from pdf_table_5.table_classification import image_table_classification


def test_large_image_with_only_caption_words_is_image_table() -> None:
    segment = {"sourceBbox": [0, 0, 100, 100]}
    words = [{"bbox": [5, 2, 20, 8], "text": "Caption"}]
    images = [[5, 15, 95, 95]]

    result = image_table_classification([(segment, words, images)])

    assert result["imageTable"] is True
    assert result["imageCoverage"] == [0.72]


def test_image_with_native_words_overlaid_is_native_text_table() -> None:
    segment = {"sourceBbox": [0, 0, 100, 100]}
    words = [{"bbox": [10, 20, 30, 30], "text": "Cell"}]
    images = [[5, 15, 95, 95]]

    result = image_table_classification([(segment, words, images)])

    assert result["imageTable"] is False
    assert result["nativeWordsInImageRegions"] == 1


def test_small_logo_does_not_make_native_region_an_image_table() -> None:
    segment = {"sourceBbox": [0, 0, 100, 100]}
    words = [{"bbox": [10, 50, 30, 60], "text": "Cell"}]
    images = [[0, 0, 20, 20]]

    result = image_table_classification([(segment, words, images)])

    assert result["imageTable"] is False
