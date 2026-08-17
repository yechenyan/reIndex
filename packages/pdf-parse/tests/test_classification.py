from pdf_parse.classification import _union_bbox


def test_uncertain_block_union_keeps_all_visual_regions():
    assert _union_bbox([[10, 20, 30, 40], [5, 70, 20, 10]]) == [5, 20, 35, 60]
