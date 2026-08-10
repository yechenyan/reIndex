from __future__ import annotations


def partition_replacements(items: list[dict]) -> tuple[list[dict], list[dict], list[int]]:
    valid = [item for item in items if item.get("accepted") and item.get("outputPath")]
    invalid = [item for item in items if item not in valid]
    blocked_pages = set().union(*(pages_for(item) for item in invalid)) if invalid else set()
    changed = True
    while changed:
        changed = False
        for item in valid:
            pages = pages_for(item)
            if pages.intersection(blocked_pages) and not pages.issubset(blocked_pages):
                blocked_pages.update(pages)
                changed = True
    eligible = [item for item in valid if not pages_for(item).intersection(blocked_pages)]
    blocked = [item for item in valid if item not in eligible]
    return eligible, blocked, sorted(blocked_pages)


def pages_for(item: dict) -> set[int]:
    return {
        int(part["page"])
        for part in item.get("tables", [])
        if part.get("page") is not None
    }
