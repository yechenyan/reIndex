from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .io_utils import atomic_json, read_json, utc_now
from .markdown import row_matrix_markdown
from .paths import ProjectPaths


def finalize_project(paths: ProjectPaths) -> dict[str, Any]:
    blocks = sorted(
        read_json(paths.helper / "documentBlocks.json"),
        key=lambda block: (block["page"], block["order"]),
    )
    parsed = read_json(paths.helper / "parsedBlocks.json", [])
    by_source = _parsed_by_source(parsed)
    emitted_tables: set[str] = set()
    markdown: list[str] = ["# Parsed document"]
    sequence = []
    for block in blocks:
        if block["ignored"]:
            continue
        parsed_blocks = by_source.get(block["blockId"], [])
        if parsed_blocks:
            for parsed_block in parsed_blocks:
                table_id = parsed_block["parseBlockId"]
                if table_id in emitted_tables:
                    continue
                emitted_tables.add(table_id)
                content, asset = _render_table(paths, parsed_block, blocks)
                markdown.extend([_anchor(block), content])
                sequence.append(
                    _metadata_node(block, "table", parsed_block["status"], asset, table_id)
                )
            continue
        content = _render_source_block(paths, block)
        if content:
            markdown.extend([_anchor(block), content])
            sequence.append(_metadata_node(block, block["liteParseType"], "liteparse", None, None))
    output_md = paths.output / "output.md"
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n\n".join(markdown).rstrip() + "\n", encoding="utf-8")
    metadata = {
        "generatedAt": utc_now(),
        "sourcePdf": read_json(paths.job)["demand"]["inputPath"],
        "coordinateSystem": read_json(paths.job)["coordinateSystem"],
        "sequence": sequence,
    }
    atomic_json(paths.output / "metadata.json", metadata)
    report = build_report(paths, parsed)
    atomic_json(paths.report / "summary.json", report)
    return report


def _parsed_by_source(parsed: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    values: dict[str, list[dict[str, Any]]] = {}
    for item in parsed:
        for source in item["sourceBlockIds"]:
            values.setdefault(source, []).append(item)
    return values


def _anchor(block: dict[str, Any]) -> str:
    bbox = ",".join(f"{value:.2f}" for value in (block.get("bbox") or []))
    return f"<!-- pdf-parse:block={block['blockId']} page={block['page']} bbox={bbox} -->"


def _render_source_block(paths: ProjectPaths, block: dict[str, Any]) -> str:
    if block["liteParseType"] != "figure":
        return block.get("markdown") or ""
    document = read_json(paths.helper / "liteparse.json")
    images = [image for image in document.get("images", []) if image["page"] == block["page"]]
    image = min(images, key=lambda item: _bbox_distance(item["bbox"], block["bbox"]), default=None)
    if not image or not image.get("path"):
        return ""
    path = Path(image["path"])
    try:
        relative = path.resolve().relative_to(paths.output.resolve())
    except ValueError:
        return ""
    return f"![Figure]({relative.as_posix()})"


def _bbox_distance(left: list[float], right: list[float]) -> float:
    return sum(abs(a - b) for a, b in zip(left, right))


def _render_table(
    paths: ProjectPaths,
    parsed: dict[str, Any],
    blocks: list[dict[str, Any]],
) -> tuple[str, str | None]:
    if parsed["status"] == "pass" and parsed.get("result"):
        result = parsed["result"]
        asset = paths.assets / f"{parsed['parseBlockId']}.csv"
        _write_csv(asset, result["rows"])
        content = row_matrix_markdown(result["rows"])
        return f"{content}\n\n[Download CSV](assets/{asset.name})", f"assets/{asset.name}"
    sources = {block["blockId"]: block for block in blocks}
    fallback = [sources[source].get("markdown") or "" for source in parsed["sourceBlockIds"] if source in sources]
    warning = f"> [!WARNING]\n> Table extraction status: `{parsed['status']}`. LiteParse fallback retained."
    return warning + "\n\n" + "\n\n".join(fallback), None


def _write_csv(path: Path, rows: list[list[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerows(rows)


def _metadata_node(block: dict[str, Any], kind: str, status: str, asset: str | None, parse_id: str | None) -> dict[str, Any]:
    return {"blockId": block["blockId"], "parseBlockId": parse_id, "type": kind, "page": block["page"], "bbox": block["bbox"], "status": status, "asset": asset}


def build_report(paths: ProjectPaths, parsed: list[dict[str, Any]]) -> dict[str, Any]:
    usage: dict[str, int] = {}
    for item in parsed:
        for key, value in item.get("usage", {}).items():
            usage[key] = usage.get(key, 0) + value
    statuses: dict[str, int] = {}
    for item in parsed:
        statuses[item["status"]] = statuses.get(item["status"], 0) + 1
    return {"generatedAt": utc_now(), "tables": len(parsed), "tableStatuses": statuses, "repairs": sum(item.get("repairs", 0) for item in parsed), "tokenUsage": usage, "problemTables": [item["parseBlockId"] for item in parsed if item["status"] in {"failed", "wrong"}]}
