from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TEXT_ITEMS = {"TextItem", "ListItem", "TitleItem", "CodeItem", "FormulaItem"}
VISUAL_ITEMS = {"PictureItem", "TableItem"}
SKIPPED_SECTIONS = {"contents", "table of contents", "inhalt"}
TEXT_CHUNK_TARGET = 12_000


@dataclass
class TextChunk:
    title: str
    path: tuple[str, ...]
    texts: list[str]
    pages: tuple[int, int] | None
    part: int = 1
    parts: int = 1


def extract_structure(
    document, excluded_pages: set[int]
) -> tuple[list[TextChunk], dict[int, dict[str, Any]]]:
    sections: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    stack: list[str] = []
    current: dict[str, Any] | None = None
    for item, raw_level in document.iterate_items():
        name = type(item).__name__
        text = getattr(item, "text", "").strip()
        pages = _pages(item)
        if name == "SectionHeaderItem" and text:
            level = max(int(raw_level or 1), 1)
            stack = stack[: level - 1]
            stack.append(text)
            current = {
                "title": text,
                "path": tuple(stack),
                "texts": [],
                "pages": set(pages),
            }
            sections.append(current)
        elif name in TEXT_ITEMS and text:
            if current is None:
                current = {
                    "title": "Document overview",
                    "path": (),
                    "texts": [],
                    "pages": set(),
                }
                sections.append(current)
            if not pages or not pages <= excluded_pages:
                current["texts"].append(text)
                current["pages"].update(pages)
        events.append({"item": item, "name": name, "text": text, "path": tuple(stack)})
    chunks = _chunks(sections)
    return chunks, _visual_contexts(events)


def _chunks(sections: list[dict[str, Any]]) -> list[TextChunk]:
    result: list[TextChunk] = []
    for section in sections:
        if (
            not section["texts"]
            or section["title"].strip().lower() in SKIPPED_SECTIONS
            or not any(
                any(character.isalnum() for character in text)
                for text in section["texts"]
            )
        ):
            continue
        groups = _paragraph_groups(section["texts"])
        pages = sorted(section["pages"])
        page_range = (pages[0], pages[-1]) if pages else None
        for part, texts in enumerate(groups, 1):
            result.append(
                TextChunk(
                    section["title"],
                    section["path"],
                    texts,
                    page_range,
                    part=part,
                    parts=len(groups),
                )
            )
    return result


def _paragraph_groups(texts: list[str]) -> list[list[str]]:
    groups: list[list[str]] = [[]]
    size = 0
    for text in texts:
        if groups[-1] and size + len(text) > TEXT_CHUNK_TARGET:
            groups.append([])
            size = 0
        groups[-1].append(text)
        size += len(text)
    return groups


def _visual_contexts(events: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    contexts: dict[int, dict[str, Any]] = {}
    for index, event in enumerate(events):
        if event["name"] not in VISUAL_ITEMS:
            continue
        before = _nearest_text(events, index, -1, event["path"])
        after = _nearest_text(events, index, 1, event["path"])
        nearby = " ".join(value for value in (before, after) if value)
        contexts[id(event["item"])] = {
            "section_path": list(event["path"]),
            "nearby_text": nearby[:600].strip(),
        }
    return contexts


def _nearest_text(
    events: list[dict[str, Any]], start: int, step: int, path: tuple[str, ...]
) -> str:
    index = start + step
    while 0 <= index < len(events):
        event = events[index]
        if event["path"] != path:
            return ""
        if event["name"] in TEXT_ITEMS and event["text"]:
            return event["text"][:300]
        index += step
    return ""


def _pages(item) -> set[int]:
    return {value.page_no for value in (getattr(item, "prov", None) or [])}
