from __future__ import annotations

from collections import Counter
from typing import Any

from .constants import PAGE_CHROME_BAND


def _in_band(block: dict[str, Any], page: dict[str, Any]) -> bool:
    bbox = block.get("bbox")
    if not bbox:
        return False
    top = bbox[1]
    bottom = top + bbox[3]
    height = page["heightPt"]
    return bottom <= height * PAGE_CHROME_BAND or top >= height * (1 - PAGE_CHROME_BAND)


def _signature(block: dict[str, Any]) -> tuple[Any, ...]:
    x, y, width, height = block["bbox"]
    return (
        block["liteParseType"],
        round(x / 6),
        round(y / 6),
        round(width / 6),
        round(height / 6),
    )


def mark_repeated_page_chrome(pages: list[dict[str, Any]]) -> None:
    candidates = [
        _signature(block)
        for page in pages
        for block in page["blocks"]
        if _in_band(block, page)
    ]
    repeated = {signature for signature, count in Counter(candidates).items() if count >= 2}
    for page in pages:
        for block in page["blocks"]:
            if _in_band(block, page) and _signature(block) in repeated:
                block["ignored"] = True
                block["ignoredReason"] = "repeated_page_chrome"
                block["needsAgent"] = False
