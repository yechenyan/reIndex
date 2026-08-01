from __future__ import annotations

from reindex_cli.parsers.common import description_for, initial_body
from reindex_cli.pipeline.models import DraftNode, SourceItem


def parse_generic(item: SourceItem) -> list[DraftNode]:
    title = item.config.title or item.path.name
    node = DraftNode(
        logical_key=item.relative,
        item_path=item.relative,
        kind="file",
        title=title,
        description=item.config.description or description_for(title, "file"),
        source_path=item.relative,
        source_sha256=item.sha256,
        content=item.path.read_bytes(),
        extension=item.path.suffix.lstrip(".") or "bin",
        media_type=item.media_type,
        warnings=[
            "No specialized parser was available; content is preserved as a file."
        ],
    )
    node.body = initial_body(node)
    return [node]
