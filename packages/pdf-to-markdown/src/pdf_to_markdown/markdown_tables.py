from __future__ import annotations

import re


SEPARATOR = re.compile(r"^:?-{3,}:?$")
CAPTION = re.compile(r"^#{1,6}\s+.*\b(?:table|tabelle)\s*\d+", re.IGNORECASE)


def page_offsets(document: str, pages: list[dict]) -> dict[int, int]:
    offsets: dict[int, int] = {}
    cursor = 0
    for page in pages:
        markdown = page["markdown"]
        start = document.find(markdown, cursor)
        if start < 0:
            raise ValueError(f"Cannot locate LiteParse markdown for page {page['page']}")
        offsets[page["page"]] = start
        cursor = start + len(markdown)
    return offsets


def find_tables(markdown: str) -> list[dict]:
    lines = positioned_lines(markdown)
    blocks, index = [], 0
    while index < len(lines):
        if not lines[index][2].lstrip().startswith("|"):
            index += 1
            continue
        end = index + 1
        while end < len(lines) and lines[end][2].lstrip().startswith("|"):
            end += 1
        block = table_block(lines[index:end])
        if block is not None:
            blocks.append(block)
        index = end
    return blocks


def table_block(lines: list[tuple[int, int, str]]) -> dict | None:
    parsed = [split_row(line.rstrip("\r\n")) for _, _, line in lines]
    if len(parsed) < 2 or not is_separator(parsed[1]):
        return None
    width = len(parsed[0])
    if width < 2 or any(len(row) != width for row in parsed):
        return None
    return {
        "start": lines[0][0],
        "end": lines[-1][1],
        "markdown": "".join(line for _, _, line in lines).rstrip("\r\n"),
        "matrix": [parsed[0], *parsed[2:]],
    }


def split_row(line: str) -> list[str]:
    stripped = line.strip()
    cells, current, escaped = [], [], False
    for character in stripped:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    cells.append("".join(current).strip())
    if stripped.startswith("|"):
        cells = cells[1:]
    if stripped.endswith("|"):
        cells = cells[:-1]
    return cells


def is_separator(row: list[str]) -> bool:
    return bool(row) and all(SEPARATOR.fullmatch(cell.replace(" ", "")) for cell in row)


def complex_page_span(markdown: str, *, continues: bool) -> tuple[int, int] | None:
    lines = positioned_lines(markdown)
    pipe_indexes = [index for index, (_, _, line) in enumerate(lines) if "|" in line]
    if not pipe_indexes:
        return None
    start_index = pipe_indexes[0]
    end = len(markdown)
    if not continues:
        for line_start, _, line in lines[pipe_indexes[-1] + 1 :]:
            if CAPTION.match(line.strip()):
                end = line_start
                break
    return lines[start_index][0], end


def positioned_lines(markdown: str) -> list[tuple[int, int, str]]:
    result, offset = [], 0
    for line in markdown.splitlines(keepends=True):
        result.append((offset, offset + len(line), line))
        offset += len(line)
    if offset < len(markdown):
        result.append((offset, len(markdown), markdown[offset:]))
    return result
