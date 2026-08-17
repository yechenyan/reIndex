from pdf_parse.geometry import expanded_bbox, intersects


def test_intersection_and_expansion_are_viewport_based():
    assert intersects([10, 10, 20, 20], [25, 25, 10, 10])
    assert not intersects([10, 10, 5, 5], [20, 20, 5, 5])
    assert expanded_bbox([5, 5, 20, 20], 100, 100, 10) == [0.0, 0.0, 35, 35]
