from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from reindex_cli.errors import ReIndexError
from reindex_cli.parsers.common import description_for, initial_body
from reindex_cli.pipeline.models import DraftNode, SourceItem

TEXT_CHUNK_TARGET = 20_000


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
    group = DraftNode(
        logical_key=item.relative,
        item_path=item.relative,
        kind="group",
        title=title,
        description=item.config.description or description_for(title, "group"),
        source_path=item.relative,
        source_sha256=item.sha256,
    )
    group.body = initial_body(group)
    nodes = [group]
    if item.config.parse["text"] == "auto":
        nodes.extend(_text_nodes(document, item, excluded_table_pages, title))
    if item.config.parse["images"] == "auto":
        nodes.extend(_image_nodes(document, item))
    if item.config.parse["tables"] == "auto":
        nodes.extend(_table_nodes(document, item))
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
    document, source: SourceItem, excluded_pages: set[int], document_title: str
) -> list[DraftNode]:
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for item, _level in document.iterate_items():
        text = getattr(item, "text", "").strip()
        pages = _pages(item)
        if not text or (pages and pages <= excluded_pages):
            continue
        name = type(item).__name__
        if name == "SectionHeaderItem":
            current = {"title": text, "texts": [], "pages": set(pages)}
            sections.append(current)
            continue
        if name not in {"TextItem", "ListItem", "TitleItem", "CodeItem", "FormulaItem"}:
            continue
        if current is None:
            current = {"title": "Document overview", "texts": [], "pages": set()}
            sections.append(current)
        current["texts"].append(text)
        current["pages"].update(pages)
    chunks: list[list[dict[str, Any]]] = []
    for section in (value for value in sections if value["texts"]):
        section_size = len(section["title"]) + sum(
            len(text) for text in section["texts"]
        )
        current_size = sum(
            len(value["title"]) + sum(len(text) for text in value["texts"])
            for value in (chunks[-1] if chunks else [])
        )
        if chunks and chunks[-1] and current_size + section_size > TEXT_CHUNK_TARGET:
            chunks.append([])
        if not chunks:
            chunks.append([])
        chunks[-1].append(section)
    result: list[DraftNode] = []
    for index, chunk in enumerate(chunks, 1):
        pages = sorted(set().union(*(section["pages"] for section in chunk)))
        content = f"# {document_title}\n\n" + "\n\n".join(
            f"## {section['title']}\n\n" + "\n\n".join(section["texts"])
            for section in chunk
        )
        content += "\n"
        title = "Document text" if len(chunks) == 1 else f"Document text — Part {index}"
        node = DraftNode(
            logical_key=f"{source.relative}#text:part:{index}",
            item_path=source.relative,
            kind="text",
            title=title,
            description=f"Consolidated readable text for {document_title}.",
            source_path=source.relative,
            source_sha256=source.sha256,
            pages=(pages[0], pages[-1]) if pages else None,
            content=content.encode(),
            extension="md",
            media_type="text/markdown",
            parent_key=source.relative,
            order_hint=((pages[0] if pages else 0), index),
        )
        node.body = initial_body(node)
        result.append(node)
    return result


def _image_nodes(document, source: SourceItem) -> list[DraftNode]:
    result = []
    for index, picture in enumerate(document.pictures, 1):
        if not picture.prov:
            continue
        provenance = picture.prov[0]
        page = document.pages[provenance.page_no]
        box = provenance.bbox
        area = abs((box.r - box.l) * (box.t - box.b))
        if area / (page.size.width * page.size.height) < 0.05:
            continue
        image = picture.get_image(document)
        if image is None:
            continue
        output = io.BytesIO()
        image.convert("RGB").save(output, format="PNG")
        title = (
            picture.caption_text(document).strip()
            or f"Image on page {provenance.page_no}"
        )
        node = DraftNode(
            logical_key=f"{source.relative}#image:{provenance.page_no}:{index}",
            item_path=source.relative,
            kind="image",
            title=title,
            description=description_for(title, "image"),
            source_path=source.relative,
            source_sha256=source.sha256,
            pages=(provenance.page_no, provenance.page_no),
            content=output.getvalue(),
            extension="png",
            media_type="image/png",
            parent_key=source.relative,
            order_hint=(provenance.page_no, index),
        )
        node.body = initial_body(node)
        result.append(node)
    return result


def _table_nodes(document, source: SourceItem) -> list[DraftNode]:
    result = []
    for index, table_item in enumerate(document.tables, 1):
        frame = table_item.export_to_dataframe(doc=document)
        csv_bytes = frame.to_csv(index=False, lineterminator="\n").encode()
        pages = sorted(_pages(table_item))
        title = table_item.caption_text(document).strip() or f"Table {index}"
        columns = [
            {"name": str(name), "type": "string", "description": f"Values for {name}."}
            for name in frame.columns
        ]
        table = {
            "row_count": len(frame),
            "grain": "One row extracted from the PDF table.",
            "columns": columns,
            "preview": frame.head(5).fillna("").astype(str).to_dict(orient="records"),
        }
        node = DraftNode(
            logical_key=f"{source.relative}#table:{index}",
            item_path=source.relative,
            kind="table",
            title=title,
            description=description_for(title, "table"),
            source_path=source.relative,
            source_sha256=source.sha256,
            pages=(pages[0], pages[-1]) if pages else None,
            content=csv_bytes,
            extension="csv",
            media_type="text/csv",
            table=table,
            parent_key=source.relative,
            order_hint=((pages[0] if pages else 0), index),
        )
        node.body = initial_body(node)
        result.append(node)
    return result


def _pages(item) -> set[int]:
    return {provenance.page_no for provenance in (getattr(item, "prov", None) or [])}
