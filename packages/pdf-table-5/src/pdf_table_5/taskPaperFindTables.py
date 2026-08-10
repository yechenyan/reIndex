from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from .agent_context import finder_images, finder_input
from .agent_schemas import FINDER_OUTPUT_SCHEMA
from .agents import run_agent
from .context import Context
from .contracts import validate_find_tables
from .io import read_json, relative, write_json
from .pdf import inspect_pdf, render_page
from .prompts_finder import finder_prompt, finder_repair_prompt


def run(context: Context) -> tuple[dict, dict[str, int]]:
    metadata = prepare(context)
    output = context.paths.helper_json("findTable.json")
    if output.exists():
        try:
            return validate_find_tables(read_json(output), metadata["pages"]), {}
        except ValueError:
            pass
    prompt_context = finder_input(metadata, context.params)
    images = finder_images(context, metadata)
    result = run_agent(
        context, "finder", finder_prompt(prompt_context), images=images, output_schema=FINDER_OUTPUT_SCHEMA
    )
    raw = result.payload["findTableJson"]
    try:
        value = validate_find_tables(json_value(raw), metadata["pages"])
    except (TypeError, ValueError) as exc:
        fixed = run_agent(
            context,
            "finder-fix",
            finder_repair_prompt(prompt_context, raw, str(exc)),
            images=images,
            output_schema=FINDER_OUTPUT_SCHEMA,
        )
        value = validate_find_tables(json_value(fixed.payload["findTableJson"]), metadata["pages"])
        result.token_usage = combined_usage(result.token_usage, fixed.token_usage)
    write_json(output, value)
    return value, result.token_usage


def prepare(context: Context) -> dict:
    info = inspect_pdf(context.pdf, context.target_pages)
    metadata = {
        "version": "pdf-table-5/find-preparation@1.0",
        "sourcePdf": str(context.pdf),
        "pageCount": info["totalPages"],
        "pageNumbering": "1-based",
        "coordinateSystem": info["coordinateSystem"],
        "pages": info["pages"],
    }
    write_json(context.paths.helper_json("taskPaperFindTables.json"), metadata)
    finder = context.paths.helper / "finder"
    pages_dir, sheets_dir = finder / "pages", finder / "sheets"
    pages_dir.mkdir(parents=True, exist_ok=True)
    sheets_dir.mkdir(parents=True, exist_ok=True)
    dpi = int(context.params.get("overviewDpi", 96))
    images = []
    for page in metadata["pages"]:
        target = pages_dir / f"page-{page['page']:04d}.png"
        if not target.exists() and not page["skipFinder"]:
            render_page(context.pdf, page["page"], target, dpi)
        if target.exists():
            page["overviewImage"] = relative(target, context.paths.project)
            with Image.open(target) as rendered:
                page["overviewImagePixels"] = {"width": rendered.width, "height": rendered.height}
            images.append((page["page"], target))
    make_sheets(images, sheets_dir, context.job.get("aggregateImages", {}))
    write_json(context.paths.helper_json("taskPaperFindTables.json"), metadata)
    return metadata


def make_sheets(images: list[tuple[int, Path]], output: Path, config: dict) -> None:
    columns = max(1, int(config.get("columns", 3)))
    per_sheet = max(1, int(config.get("maxPagesPerSheet", 12)))
    thumb_width, label_height, gap = 360, 28, 12
    for sheet_index in range(math.ceil(len(images) / per_sheet)):
        batch = images[sheet_index * per_sheet : (sheet_index + 1) * per_sheet]
        thumbs = []
        for page, path in batch:
            image = Image.open(path).convert("RGB")
            height = round(image.height * thumb_width / image.width)
            thumbs.append((page, image.resize((thumb_width, height))))
        row_height = max((image.height for _, image in thumbs), default=1) + label_height
        rows = math.ceil(len(thumbs) / columns)
        sheet = Image.new("RGB", (columns * (thumb_width + gap) + gap, rows * (row_height + gap) + gap), "white")
        draw = ImageDraw.Draw(sheet)
        for index, (page, image) in enumerate(thumbs):
            x = gap + index % columns * (thumb_width + gap)
            y = gap + index // columns * (row_height + gap)
            draw.text((x, y), f"Page {page}", fill="black")
            sheet.paste(image, (x, y + label_height))
        sheet.save(output / f"sheet-{sheet_index + 1:03d}.jpg", quality=88)


def json_value(raw: str) -> dict:
    import json

    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Finder output must be a JSON object")
    return value


def combined_usage(first: dict[str, int], second: dict[str, int]) -> dict[str, int]:
    keys = first.keys() | second.keys()
    return {key: first.get(key, 0) + second.get(key, 0) for key in keys}
