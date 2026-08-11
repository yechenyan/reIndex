from __future__ import annotations

import csv
import io
import re
from collections import Counter

from reindex_cli.parsers.common import initial_body
from reindex_cli.parsers.markdown import HEADING
from reindex_cli.parsers.table_profile import build_table_profile, table_columns
from reindex_cli.pipeline.models import DraftNode, SourceItem
from reindex_cli.util import slugify

TABLE_RULE = re.compile(r"^:?-{3,}:?$")
IMAGE = re.compile(r"^\s*!\[[^]]*]\([^)]*\)\s*$")
def is_nap_markdown(item: SourceItem) -> bool:
    return (item.path.name == "output.md" or item.path.name.startswith(".nap-markdown")) and (
        "pdf-to-markdown" in item.path.parent.name or item.config.derived_from is not None
    )
def parse_nap_markdown(item: SourceItem) -> list[DraftNode]:
    text = item.path.read_text(encoding="utf-8").replace("\r\n", "\n")
    lines = text.splitlines(keepends=True)
    source_path = item.config.derived_from or item.relative
    source_sha256 = item.sha256 if source_path == item.relative else None
    clean = ["\n" if IMAGE.match(line) else line for line in lines]
    sections = _sections(clean)
    title = item.config.title or _document_title(text, item.path.stem)
    group = DraftNode(
        logical_key=item.relative,
        item_path=item.relative,
        kind="group",
        title=title,
        description=item.config.description
        or f"NAP Markdown document containing {len(sections)} top-level chapters.",
        source_path=source_path, source_sha256=source_sha256,
    )
    group.body = initial_body(group)
    return [group, *_text_nodes(item, title, sections, source_path, source_sha256)]

class _Table:
    def __init__(self, start: int, end: int, headers: list[str], rows: list[list[str]], title: str, path: tuple[str, ...]):
        self.start, self.end = start, end
        self.headers, self.rows, self.title, self.path = headers, rows, title, path
def _tables(lines: list[str]) -> list[_Table]:
    result: list[_Table] = []
    path: list[str] = []
    index = 0
    while index < len(lines):
        match = HEADING.match(lines[index].rstrip("\n"))
        if match:
            level, title = len(match.group(1)), match.group(2).strip()
            path = path[: level - 1] + [title]
        if not _table_start(lines, index):
            index += 1
            continue
        start, headers = index, _cells(lines[index])
        index += 2
        rows: list[list[str]] = []
        while index < len(lines) and _pipe_line(lines[index]):
            row = _cells(lines[index])
            if len(row) != len(headers):
                break
            rows.append(row)
            index += 1
        result.append(_Table(start, index, _headers(headers), rows, _table_title(lines, start, len(result) + 1, path), tuple(path)))
    return result

def _table_start(lines: list[str], index: int) -> bool:
    return index + 1 < len(lines) and _pipe_line(lines[index]) and _is_rule(_cells(lines[index + 1]))
def _pipe_line(line: str) -> bool:
    value = line.strip()
    return value.startswith("|") and value.endswith("|")


def _is_rule(cells: list[str]) -> bool:
    return bool(cells) and all(TABLE_RULE.fullmatch(cell.strip()) for cell in cells)


def _cells(line: str) -> list[str]:
    value = line.strip()[1:-1]
    cells, current, escaped = [], [], False
    for character in value:
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
    if escaped:
        current.append("\\")
    cells.append("".join(current).strip())
    return cells


def _headers(raw: list[str]) -> list[str]:
    counts: Counter[str] = Counter()
    result = []
    for index, value in enumerate(raw, 1):
        base = value or f"Column {index}"
        counts[base] += 1
        result.append(base if counts[base] == 1 else f"{base} ({counts[base]})")
    return result


def _table_title(lines: list[str], start: int, number: int, path: list[str]) -> str:
    for line in reversed(lines[max(0, start - 16) : start]):
        value = line.strip().lstrip("#").strip()
        if re.fullmatch(r"[-_=]{3,}", value):
            continue
        if value and "|" not in value and len(value) <= 100 and not value.endswith((".", ":")):
            return value
    return path[-1] if path else f"NAP table {number}"


def _sections(lines: list[str]) -> list[tuple[int, tuple[str, ...], str]]:
    result: list[tuple[int, tuple[str, ...], str]] = []
    path: list[str] = []
    current_path: tuple[str, ...] = ()
    start, content = 0, []
    for index, line in enumerate(lines):
        match = HEADING.match(line.rstrip("\n"))
        if match and len(match.group(1)) == 1:
            if current_path and _has_body(content):
                result.append((start, current_path, "".join(content)))
            level, title = len(match.group(1)), match.group(2).strip()
            path = path[: level - 1] + [title]
            current_path, start, content = tuple(path), index, [line]
        else:
            content.append(line)
    if current_path and _has_body(content):
        result.append((start, current_path, "".join(content)))
    return result


def _has_body(lines: list[str]) -> bool:
    values = list(lines)
    if values and HEADING.match(values[0].rstrip("\n")):
        values = values[1:]
    return bool("".join(values).strip())


def _document_title(text: str, stem: str) -> str:
    for line in text.splitlines()[:100]:
        value = line.strip().lstrip("#").strip()
        if "netzausbauplan" in value.lower() and len(value) <= 120:
            return value
    return stem.replace("_", " ").replace("-", " ").strip()


def _text_nodes(item: SourceItem, title: str, sections: list[tuple[int, tuple[str, ...], str]], source_path: str, source_sha256: str | None) -> list[DraftNode]:
    counts: Counter[str] = Counter()
    result = []
    for order, (start, path, text) in enumerate(sections, 1):
        section_title = path[-1] if path else f"Text part {order}"
        key = slugify("-".join(path) or section_title, "section")
        counts[key] += 1
        suffix = f":{counts[key]}" if counts[key] > 1 else ""
        node = DraftNode(
            logical_key=f"{item.relative}#text:{key}{suffix}", item_path=item.relative,
            kind="text", title=section_title,
            description=f"Text from the “{' > '.join(path) or section_title}” section of {title}.",
            source_path=source_path, source_sha256=source_sha256, content=text.encode(),
            extension="md", media_type="text/markdown", parent_key=item.relative,
            order_hint=(start,), context={"section_path": list(path)},
        )
        node.body = initial_body(node)
        result.append(node)
    return result


def _table_nodes(item: SourceItem, tables: list[_Table], source_path: str, source_sha256: str | None, parents: dict[str, str]) -> list[DraftNode]:
    result = []
    titles = Counter(table.title for table in tables)
    for number, source in enumerate(tables, 1):
        parent_key = parents.get(source.path[0], item.relative) if source.path else item.relative
        output = io.StringIO(newline="")
        csv.writer(output, lineterminator="\n").writerows([source.headers, *source.rows])
        profile = build_table_profile(source.headers, source.rows)
        node = DraftNode(
            logical_key=f"{item.relative}#table:{number}", item_path=item.relative,
            kind="table", title=(source.title if titles[source.title] == 1 else f"{source.title} — Table {number}"),
            description=f"NAP table with {len(source.rows)} rows and {len(source.headers)} columns.",
            source_path=source_path, source_sha256=source_sha256, content=output.getvalue().encode(),
            extension="csv", media_type="text/csv", parent_key=parent_key,
            order_hint=(source.start,), context={"section_path": list(source.path)},
            table={"row_count": len(source.rows), "grain": "One row from the source table.",
                   "columns": table_columns(profile), "profile": profile,
                   "preview": [dict(zip(source.headers, row, strict=True)) for row in source.rows[:5]]},
        )
        node.body = initial_body(node)
        result.append(node)
    return result
