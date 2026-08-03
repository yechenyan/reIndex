from __future__ import annotations

import io

from reindex_cli.parsers.common import initial_body
from reindex_cli.parsers.table_profile import build_table_profile, table_columns
from reindex_cli.pipeline.models import DraftNode, SourceItem


def image_nodes(
    document, source: SourceItem, document_title: str, contexts: dict
) -> list[DraftNode]:
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
        caption = picture.caption_text(document).strip()
        title = caption or f"Image on page {provenance.page_no}"
        context = dict(contexts.get(id(picture), {}))
        context.update({"width": image.width, "height": image.height})
        section = " > ".join(context.get("section_path", []))
        description = (
            f"Image captioned “{caption}” in {document_title}."
            if caption
            else f"Image from {section or document_title} on page {provenance.page_no}."
        )
        node = DraftNode(
            logical_key=f"{source.relative}#image:{provenance.page_no}:{index}",
            item_path=source.relative,
            kind="image",
            title=title,
            description=description,
            source_path=source.relative,
            source_sha256=source.sha256,
            pages=(provenance.page_no, provenance.page_no),
            content=output.getvalue(),
            extension="png",
            media_type="image/png",
            parent_key=source.relative,
            order_hint=(provenance.page_no, index),
            context=context,
        )
        node.body = initial_body(node)
        result.append(node)
    return result


def table_nodes(
    document, source: SourceItem, document_title: str, contexts: dict
) -> list[DraftNode]:
    result = []
    for index, table_item in enumerate(document.tables, 1):
        frame = table_item.export_to_dataframe(doc=document).fillna("").astype(str)
        headers = [str(value) for value in frame.columns]
        rows = frame.values.tolist()
        profile = build_table_profile(headers, rows)
        pages = sorted(_pages(table_item))
        caption = table_item.caption_text(document).strip()
        title = caption or f"Table {index}"
        context = dict(contexts.get(id(table_item), {}))
        section = " > ".join(context.get("section_path", []))
        node = DraftNode(
            logical_key=f"{source.relative}#table:{index}",
            item_path=source.relative,
            kind="table",
            title=title,
            description=f"Table from {section or document_title} in {document_title}.",
            source_path=source.relative,
            source_sha256=source.sha256,
            pages=(pages[0], pages[-1]) if pages else None,
            content=frame.to_csv(index=False, lineterminator="\n").encode(),
            extension="csv",
            media_type="text/csv",
            table={
                "row_count": len(rows),
                "grain": "One row extracted from the PDF table.",
                "columns": table_columns(profile),
                "profile": profile,
                "preview": frame.head(5).to_dict(orient="records"),
            },
            parent_key=source.relative,
            order_hint=((pages[0] if pages else 0), index),
            context=context,
        )
        node.body = initial_body(node)
        result.append(node)
    return result


def _pages(item) -> set[int]:
    return {value.page_no for value in (getattr(item, "prov", None) or [])}
