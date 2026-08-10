from __future__ import annotations

from collections.abc import Iterable


PageSelection = str | Iterable[int] | None


def normalize_pages(value: PageSelection, total_pages: int) -> list[int] | None:
    if value is None:
        return None
    pages = parse_expression(value) if isinstance(value, str) else list(value)
    if not pages:
        raise ValueError("Page selection cannot be empty")
    if any(type(page) is not int for page in pages):
        raise ValueError("Page selection must contain integers")
    normalized = sorted(set(pages))
    outside = [page for page in normalized if not 1 <= page <= total_pages]
    if outside:
        raise ValueError(f"Pages outside 1..{total_pages}: {outside}")
    return normalized


def parse_expression(value: str) -> list[int]:
    pages: list[int] = []
    for raw in value.split(","):
        part = raw.strip()
        if not part:
            raise ValueError(f"Invalid page selection: {value!r}")
        if "-" not in part:
            pages.append(parse_positive(part, value))
            continue
        bounds = part.split("-")
        if len(bounds) != 2:
            raise ValueError(f"Invalid page range: {part!r}")
        start, end = (parse_positive(item.strip(), value) for item in bounds)
        if end < start:
            raise ValueError(f"Descending page range: {part!r}")
        pages.extend(range(start, end + 1))
    return pages


def parse_positive(value: str, expression: str) -> int:
    try:
        page = int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid page selection: {expression!r}") from exc
    if page < 1:
        raise ValueError(f"Page numbers are 1-based: {page}")
    return page
