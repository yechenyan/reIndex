from __future__ import annotations

import re
from collections import Counter

from reindex_cli.parsers.common import description_for, initial_body
from reindex_cli.pipeline.models import DraftNode, SourceItem
from reindex_cli.util import slugify

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def parse_markdown(item: SourceItem) -> list[DraftNode]:
    content = item.path.read_bytes().replace(b"\r\n", b"\n")
    text = content.decode("utf-8")
    sections = _sections(text)
    heading = next((value[0][-1] for value in sections if value[0]), None)
    title = item.config.title or heading or _title(item.path.stem)
    meaningful = [value for value in sections if _has_body(value[1])]
    if len(meaningful) <= 1:
        node = DraftNode(
            logical_key=item.relative,
            item_path=item.relative,
            kind="text",
            title=title,
            description=item.config.description or _document_description(title, text),
            source_path=item.relative,
            source_sha256=item.sha256,
            content=content,
            extension="md",
            media_type="text/markdown",
            context={"section_path": list(meaningful[0][0]) if meaningful else []},
        )
        node.body = initial_body(node)
        return [node]
    group = DraftNode(
        logical_key=item.relative,
        item_path=item.relative,
        kind="group",
        title=title,
        description=item.config.description
        or f"Text document containing {len(meaningful)} sections.",
        source_path=item.relative,
        source_sha256=item.sha256,
    )
    group.body = initial_body(group)
    nodes = [group]
    counts: Counter[str] = Counter()
    for order, (path, section_text) in enumerate(meaningful, 1):
        section_title = path[-1] if path else f"Text part {order}"
        key = slugify("-".join(path) or section_title, "section")
        counts[key] += 1
        suffix = f":{counts[key]}" if counts[key] > 1 else ""
        node = DraftNode(
            logical_key=f"{item.relative}#text:{key}{suffix}",
            item_path=item.relative,
            kind="text",
            title=section_title,
            description=f"Text from the “{' > '.join(path) or section_title}” section of {title}.",
            source_path=item.relative,
            source_sha256=item.sha256,
            content=section_text.encode(),
            extension="md",
            media_type="text/markdown",
            parent_key=item.relative,
            order_hint=(order,),
            context={"section_path": list(path)},
        )
        node.body = initial_body(node)
        nodes.append(node)
    return nodes


def _sections(text: str) -> list[tuple[tuple[str, ...], str]]:
    result: list[tuple[tuple[str, ...], str]] = []
    path: list[str] = []
    lines: list[str] = []
    current_path: tuple[str, ...] = ()
    for line in text.splitlines(keepends=True):
        match = HEADING.match(line.rstrip("\n"))
        if match:
            if lines:
                result.append((current_path, "".join(lines)))
            level, title = len(match.group(1)), match.group(2).strip()
            path = path[: level - 1]
            path.append(title)
            current_path = tuple(path)
            lines = [line]
        else:
            lines.append(line)
    if lines:
        result.append((current_path, "".join(lines)))
    return result


def _title(stem: str) -> str:
    return stem.replace("_", " ").replace("-", " ").strip()


def _has_body(text: str) -> bool:
    lines = text.splitlines()
    if lines and HEADING.match(lines[0]):
        lines = lines[1:]
    return bool("\n".join(lines).strip())


def _document_description(title: str, text: str) -> str:
    paragraphs = [
        " ".join(value.split())
        for value in re.split(r"\n\s*\n", text)
        if value.strip() and not HEADING.match(value.strip())
    ]
    if not paragraphs:
        return description_for(title, "text")
    excerpt = paragraphs[0][:180].rstrip()
    return f"Text titled {title}; opening content: {excerpt}"
