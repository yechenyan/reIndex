from __future__ import annotations

def intersects(left: list[float], right: list[float]) -> bool:
    lx, ly, lw, lh = left
    rx, ry, rw, rh = right
    return lx < rx + rw and lx + lw > rx and ly < ry + rh and ly + lh > ry


def expanded_bbox(
    bbox: list[float],
    page_width: float,
    page_height: float,
    margin: float,
) -> list[float]:
    x, y, width, height = bbox
    left = max(0.0, x - margin)
    top = max(0.0, y - margin)
    right = min(page_width, x + width + margin)
    bottom = min(page_height, y + height + margin)
    return [left, top, right - left, bottom - top]
