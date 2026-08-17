from pdf_parse.markdown import row_matrix_markdown


def test_physical_rows_render_without_semantic_header():
    result = row_matrix_markdown([["Name", "Value"], ["A", "1"]])
    assert "<thead>" not in result
    assert result.count("<tr>") == 2
    assert "<td>Name</td>" in result
