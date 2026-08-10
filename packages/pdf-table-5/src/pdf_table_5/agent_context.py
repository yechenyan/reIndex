from __future__ import annotations

import json
from pathlib import Path

from .context import Context
from .geometry_hints import left_edge_hints, line_evidence
from .io import read_json, write_json
from .strategy_context import strategy_catalog
from .table_classification import image_table_classification


BOUNDARY_EVIDENCE_MIN_SEGMENTS = 4


def compact_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def finder_input(metadata: dict, params: dict) -> dict:
    return {
        "version": "pdf-table-5/finder-context@1.0",
        "pageNumbering": metadata["pageNumbering"],
        "coordinateSystem": metadata["coordinateSystem"],
        "recommendedTableDpi": int(params.get("tableDpi", 216)),
        "bboxGuidance": {
            "precision": "approximate",
            "marginPt": max(72, int(params.get("bboxMarginPt", 72))),
            "purpose": "include the whole table, caption, and safe surrounding space",
        },
        "pages": metadata["pages"],
    }


def finder_images(context: Context, metadata: dict) -> list[Path]:
    return [
        context.paths.project / page["overviewImage"]
        for page in metadata["pages"]
        if page.get("overviewImage") and not page.get("skipFinder")
    ]


def merge_images(context: Context, packet: dict) -> list[Path]:
    paths = []
    for pair in packet.get("possiblePairs", []):
        paths.extend(context.paths.project / name for name in pair.get("comparisonImages", []))
    return paths


def parser_input(context: Context, packet: dict) -> dict:
    evidence = []
    geometry_hints = []
    geometry_files = []
    image_files = []
    vector_words = 0
    image_count = 0
    classification_items = []
    selected = full_evidence_indexes(len(packet["tables"]))
    attachment_numbers = {item: number for number, item in enumerate(sorted(selected), start=1)}
    for index, segment in enumerate(packet["tables"]):
        geometry_path = (context.paths.project / segment["geometry"]).resolve()
        geometry = read_json(geometry_path, {})
        words = geometry.get("words", [])
        images = geometry.get("images", [])
        vector_words += len(words)
        image_count += len(images)
        classification_items.append((segment, words, images))
        geometry_files.append(
            {
                "page": segment["page"],
                "bbox": segment.get("bbox"),
                "sourceBbox": segment.get("sourceBbox"),
                "projectRelativePath": segment["geometry"],
                "absolutePath": str(geometry_path),
                "wordCount": len(words),
                "imageCount": len(images),
            }
        )
        table_image = (context.paths.project / segment["screenshot"]).resolve()
        context_image = (context.paths.project / segment["contextScreenshot"]).resolve()
        image_files.append(
            {
                "page": segment["page"],
                "table": {"absolutePath": str(table_image), "pixels": segment.get("screenshotPixels", {})},
                "pageContext": {
                    "absolutePath": str(context_image), "pixels": segment.get("contextPixels", {})
                },
            }
        )
        if index not in selected:
            continue
        geometry_hints.append(left_edge_hints(segment, words))
        evidence.append(
            {
                "page": segment["page"],
                "bbox": segment["bbox"],
                "lines": line_evidence(words),
                "images": images,
                "attachments": {
                    "table": f"attachment {attachment_numbers[index]}",
                    "pageContext": "available on demand through runtimePaths.imageFiles",
                    "tablePixels": segment.get("screenshotPixels", {}),
                    "contextPixels": segment.get("contextPixels", {}),
                },
            }
        )
    table_id = packet["parseTableId"]
    table_dir = context.paths.table_dir(table_id).resolve()
    scratch_dir = (context.paths.report / "agent-work" / table_id).resolve()
    scratch_dir.mkdir(parents=True, exist_ok=True)
    classification = image_table_classification(classification_items)
    value = {
        "version": "pdf-table-5/parser-context@1.0",
        "tablePacket": prompt_packet(packet),
        "evidenceEncoding": {
            "lineFormat": ["y0", "y1", "words"],
            "wordFormat": ["x0", "x1", "text", "block", "line", "word"],
            "expandsToRuntimeWord": ["x0", "y0", "x1", "y1", "text", "block", "line", "word"],
        },
        "evidenceMode": {
            "mode": "boundary" if len(selected) < len(packet["tables"]) else "complete",
            "segmentCount": len(packet["tables"]),
            "fullEvidenceIndexes": sorted(selected),
            "allSegmentsLoadAtRuntime": True,
        },
        "evidence": evidence,
        "geometryHints": {
            "purpose": "left-edge lines for included evidence; runtime geometry files remain authoritative for all segments",
            "segments": geometry_hints,
        },
        "availableStrategies": strategy_catalog(context.paths.strategy),
        "runtimePaths": {
            "projectRoot": str(context.paths.project.resolve()),
            "sourcePdf": str(context.pdf.resolve()),
            "tableDir": str(table_dir),
            "tableJson": str(table_dir / "table.json"),
            "parserContext": str(table_dir / "parserContext.json"),
            "scratchDir": str(scratch_dir),
            "testCommand": (
                f'python "{table_dir / "parse.py"}" --table-json "{table_dir / "table.json"}" '
                f'--output "{scratch_dir / "candidate.csv"}"'
            ),
            "geometryFiles": geometry_files,
            "imageFiles": image_files,
        },
        "runtimeClassification": {
            "vectorWordCount": vector_words,
            "imageCount": image_count,
            **classification,
        },
        "runtimeGeometryLoader": {
            "module": "pdf_table_5.runtime_geometry",
            "function": "load_segments(table_json)",
            "textFunction": "join_word_text(ordered_compact_words)",
            "segmentType": "dict; access words as segment['words']",
            "wordFormat": ["x0", "y0", "x1", "y1", "text", "block", "line", "word"],
        },
        "parserCli": "python parse.py --table-json table.json --output /absolute/output.csv",
    }
    write_json(context.paths.table_dir(packet["parseTableId"]) / "parserContext.json", value)
    return value


def prompt_packet(packet: dict) -> dict:
    fields = ("version", "parseTableId", "findTableIds", "titleHint", "coordinateSystem")
    value = {key: packet.get(key) for key in fields if key in packet}
    value["tables"] = [
        {
            key: segment.get(key)
            for key in ("findTableId", "page", "sourceBbox", "bbox", "recommendedDpi", "extractionDpi", "title")
            if key in segment
        }
        for segment in packet["tables"]
    ]
    return value


def parser_images(context: Context, packet: dict, *, include_context: bool = False) -> list[Path]:
    result, seen = [], set()
    selected = full_evidence_indexes(len(packet["tables"]))
    for index, segment in enumerate(packet["tables"]):
        if index not in selected:
            continue
        names = [segment["screenshot"]]
        if include_context:
            names.append(segment["contextScreenshot"])
        for name in names:
            path = (context.paths.project / name).resolve()
            if path not in seen:
                result.append(path)
                seen.add(path)
    return result


def full_evidence_indexes(count: int) -> set[int]:
    if count >= BOUNDARY_EVIDENCE_MIN_SEGMENTS:
        return {0, count - 1}
    return set(range(count))
