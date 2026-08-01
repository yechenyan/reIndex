from __future__ import annotations

import re

from reindex_cli.parsers.common import description_for, initial_body
from reindex_cli.pipeline.models import DraftNode, SourceItem


def parse_markdown(item: SourceItem) -> list[DraftNode]:
    content = item.path.read_bytes()
    text = content.decode("utf-8")
    heading = next(
        (
            match.group(1).strip()
            for line in text.splitlines()
            if (match := re.match(r"^#\s+(.+)$", line))
        ),
        None,
    )
    title = (
        item.config.title
        or heading
        or item.path.stem.replace("_", " ").replace("-", " ").strip()
    )
    node = DraftNode(
        logical_key=item.relative,
        item_path=item.relative,
        kind="text",
        title=title,
        description=item.config.description or description_for(title, "text"),
        source_path=item.relative,
        source_sha256=item.sha256,
        content=content.replace(b"\r\n", b"\n"),
        extension="md",
        media_type="text/markdown",
    )
    node.body = initial_body(node)
    return [node]
