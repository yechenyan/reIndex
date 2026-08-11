from __future__ import annotations

import csv
import re
from collections.abc import Iterable

from reindex_server.domain import Node, SearchUnit
from reindex_server.qwen_chunking import split_markdown_section
from reindex_server.storage import ObjectStore


def build_search_units(nodes: Iterable[Node], store: ObjectStore) -> list[SearchUnit]:
    units: list[SearchUnit] = []
    for node in nodes:
        card = node.link("card")
        units.extend(
            _text_units(
                node, "card", node.card_markdown, card.resource.id if card else None
            )
        )
        content = node.link("content")
        if not content:
            continue
        media_type = content.resource.media_type.split(";", 1)[0]
        if node.kind == "table":
            with (
                store.materialize(content.resource.object_key) as path,
                path.open(encoding="utf-8", newline="") as stream,
            ):
                for number, row in enumerate(csv.DictReader(stream), 1):
                    text = " | ".join(f"{name}: {value}" for name, value in row.items())
                    units.append(
                        _unit(
                            node,
                            "table_row",
                            text,
                            number,
                            content.resource.id,
                            row=number,
                        )
                    )
        elif media_type in {"text/markdown", "text/plain"}:
            with store.open(content.resource.object_key) as stream:
                text = stream.read().decode("utf-8")
            chunks = (
                qwen_markdown_chunks(text)
                if node.kind == "text"
                else markdown_chunks(text)
            )
            units.extend(
                _text_units(node, "content_text", text, content.resource.id, chunks)
            )
    return units


def _text_units(
    node: Node, unit_type: str, text: str, resource_id: str | None, chunks=None
) -> list[SearchUnit]:
    return [
        _unit(
            node, unit_type, value, ordinal, resource_id, start_line=start, end_line=end
        )
        for ordinal, (value, start, end) in enumerate(
            chunks or markdown_chunks(text), 1
        )
    ]


def _unit(
    node,
    unit_type,
    text,
    ordinal,
    resource_id,
    *,
    row=None,
    start_line=None,
    end_line=None,
):
    return SearchUnit(
        id=f"{node.id}:{unit_type}:{ordinal}",
        node_id=node.id,
        unit_type=unit_type,
        contextual_text=f"{node.title}\n{node.description}\n{text}",
        original_text=text,
        start_line=start_line,
        end_line=end_line,
        ordinal=ordinal,
        row=row,
        locator=node.locator,
        resource_id=resource_id,
    )


def qwen_markdown_chunks(body: str) -> list[tuple[str, int, int]]:
    return [(chunk, 1, len(body.splitlines())) for chunk in split_markdown_section(body)]


def markdown_chunks(body: str, target_tokens: int = 600, overlap_tokens: int = 80):
    lines = body.splitlines()
    if not lines:
        return [("", 1, 1)]
    blocks, current, start = [], [], 1
    for number, line in enumerate(lines, 1):
        if not line.strip() and current:
            blocks.append((current, start, number - 1))
            current = []
        else:
            if not current:
                start = number
            current.append(line)
    if current:
        blocks.append((current, start, len(lines)))
    chunks, pending, count = [], [], 0
    for block in blocks:
        block_count = len(re.findall(r"\S+", "\n".join(block[0])))
        if pending and count + block_count > target_tokens:
            chunks.append(_join(pending))
            pending, count = _overlap(pending, overlap_tokens)
        pending.append(block)
        count += block_count
    if pending:
        chunks.append(_join(pending))
    return chunks


def _join(blocks):
    return (
        "\n\n".join("\n".join(block[0]) for block in blocks),
        blocks[0][1],
        blocks[-1][2],
    )


def _overlap(blocks, target):
    result, count = [], 0
    for block in reversed(blocks):
        result.insert(0, block)
        count += len(re.findall(r"\S+", "\n".join(block[0])))
        if count >= target:
            break
    return result, count
