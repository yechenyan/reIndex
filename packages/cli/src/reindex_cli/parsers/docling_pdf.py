from __future__ import annotations

from collections import Counter
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from reindex_cli.errors import ReIndexError
from reindex_cli.parsers.common import initial_body
from reindex_cli.parsers.docling_media import image_nodes, table_nodes
from reindex_cli.parsers.docling_structure import TextChunk, extract_structure
from reindex_cli.pipeline.models import DraftNode, SourceItem
from reindex_cli.util import slugify


def parse_pdf(item: SourceItem, excluded_table_pages: set[int]) -> list[DraftNode]:
    document = _convert(
        item.path, ocr=False, tables=item.config.parse["tables"] == "auto"
    )
    if not _has_text(document):
        document = _convert(
            item.path, ocr=True, tables=item.config.parse["tables"] == "auto"
        )
    if excluded_table_pages and max(excluded_table_pages) > len(document.pages):
        raise ReIndexError(
            f"external table pages exceed PDF page count: {item.relative}"
        )
    title = item.config.title or _document_title(document, item.path.stem)
    sections, contexts = extract_structure(document, excluded_table_pages)
    group = DraftNode(
        logical_key=item.relative,
        item_path=item.relative,
        kind="group",
        title=title,
        description=item.config.description
        or f"PDF document containing {len(sections)} text sections.",
        source_path=item.relative,
        source_sha256=item.sha256,
    )
    group.body = initial_body(group)
    nodes = [group]
    if item.config.parse["text"] == "auto":
        nodes.extend(_text_nodes(sections, item, title))
    if item.config.parse["images"] == "auto":
        nodes.extend(image_nodes(document, item, title, contexts))
    if item.config.parse["tables"] == "auto":
        nodes.extend(table_nodes(document, item, title, contexts))
    return nodes


def _convert(path: Path, *, ocr: bool, tables: bool):
    options = PdfPipelineOptions(
        do_ocr=ocr,
        do_table_structure=tables,
        generate_picture_images=True,
        images_scale=2.0,
    )
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )
    return converter.convert(path).document


def _has_text(document) -> bool:
    return sum(len(getattr(item, "text", "").strip()) for item in document.texts) >= 40


def _document_title(document, fallback: str) -> str:
    for item, _level in document.iterate_items():
        if (
            type(item).__name__ == "SectionHeaderItem"
            and getattr(item, "text", "").strip()
        ):
            return item.text.strip()
    return fallback.replace("_", " ").replace("-", " ").strip()


def _text_nodes(
    chunks: list[TextChunk], source: SourceItem, document_title: str
) -> list[DraftNode]:
    counts: Counter[str] = Counter()
    result = []
    for order, chunk in enumerate(chunks, 1):
        key = slugify("-".join(chunk.path) or chunk.title, "section")
        counts[key] += 1
        suffix = f":{counts[key]}" if counts[key] > 1 else ""
        part = f":part:{chunk.part}" if chunk.parts > 1 else ""
        title = (
            chunk.title if chunk.parts == 1 else f"{chunk.title} — Part {chunk.part}"
        )
        content = _section_markdown(document_title, chunk)
        node = DraftNode(
            logical_key=f"{source.relative}#text:{key}{suffix}{part}",
            item_path=source.relative,
            kind="text",
            title=title,
            description=_section_description(chunk, document_title),
            source_path=source.relative,
            source_sha256=source.sha256,
            pages=chunk.pages,
            content=content.encode(),
            extension="md",
            media_type="text/markdown",
            parent_key=source.relative,
            order_hint=((chunk.pages or (0, 0))[0], order),
            context={"section_path": list(chunk.path)},
        )
        node.body = initial_body(node)
        result.append(node)
    return result


def _section_markdown(document_title: str, chunk: TextChunk) -> str:
    headings = "\n\n".join(
        f"{'#' * min(index + 2, 6)} {value}" for index, value in enumerate(chunk.path)
    )
    return f"# {document_title}\n\n{headings}\n\n" + "\n\n".join(chunk.texts) + "\n"


def _section_description(chunk: TextChunk, document_title: str) -> str:
    path = " > ".join(chunk.path) or chunk.title
    return f"Text from the “{path}” section of {document_title}."
