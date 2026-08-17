from pdf_parse.finalize import _parsed_by_source


def test_multiple_logical_tables_can_share_one_liteparse_source_block():
    first = {"parseBlockId": "table-0002", "sourceBlockIds": ["p0005-b0009"]}
    second = {"parseBlockId": "table-0003", "sourceBlockIds": ["p0005-b0009"]}

    values = _parsed_by_source([first, second])

    assert values["p0005-b0009"] == [first, second]
