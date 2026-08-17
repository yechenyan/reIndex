from pdf_parse.table_records import replace_usage


def test_session_usage_replaces_previous_cumulative_checkpoint():
    usage = {"input_tokens": 100, "output_tokens": 10}
    replace_usage(usage, {"input_tokens": 150, "output_tokens": 18})
    assert usage == {"input_tokens": 150, "output_tokens": 18}
