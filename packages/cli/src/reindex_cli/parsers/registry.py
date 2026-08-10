from __future__ import annotations

import json
from importlib.metadata import version

from reindex_cli.parsers.csv_parser import parse_csv
from reindex_cli.parsers.docling_pdf import parse_pdf
from reindex_cli.parsers.generic import parse_generic
from reindex_cli.parsers.markdown import parse_markdown
from reindex_cli.parsers.nap_markdown import is_nap_markdown, parse_nap_markdown
from reindex_cli.pipeline.models import DraftNode, SourceItem
from reindex_cli.util import sha256_bytes


def parse_item(item: SourceItem, excluded_table_pages: set[int]) -> list[DraftNode]:
    suffix = item.path.suffix.lower()
    if suffix == ".pdf":
        if all(setting == "off" for setting in item.config.parse.values()):
            return parse_generic(item)
        return parse_pdf(item, excluded_table_pages)
    if suffix in {".md", ".markdown", ".txt"}:
        if item.config.parse["text"] == "off":
            return parse_generic(item)
        if suffix == ".md" and is_nap_markdown(item):
            return parse_nap_markdown(item)
        return parse_markdown(item)
    if suffix == ".csv":
        if item.config.parse["tables"] == "off":
            return parse_generic(item)
        return parse_csv(item)
    return parse_generic(item)


def parser_cache_key(item: SourceItem, excluded_table_pages: set[int]) -> str:
    parser_version = version("docling") if item.path.suffix.lower() == ".pdf" else "1"
    value = {
        "source": item.sha256,
        "path": item.relative,
        "parse": item.config.parse,
        "pages": sorted(excluded_table_pages),
        "parser": parser_version,
        "implementation": 6,
        "config": {
            "title": item.config.title,
            "description": item.config.description,
            "part_of": item.config.part_of,
            "derived_from": item.config.derived_from,
            "item_pages": item.config.pages,
            "quality": item.config.quality,
        },
    }
    return sha256_bytes(
        json.dumps(value, sort_keys=True, ensure_ascii=False, default=list).encode()
    )
