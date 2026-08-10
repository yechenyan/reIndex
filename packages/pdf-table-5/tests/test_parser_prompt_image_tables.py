from pdf_table_5.prompts_parser import fixed_prefix


def test_caption_labels_do_not_make_image_tables_skippable() -> None:
    prompt = fixed_prefix()
    assert "`Abb.`, `Figure`, or `Screenshot`" in prompt
    assert "skip only when the image contains no target table data" in prompt
